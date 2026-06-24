-- =============================================================================
-- Database Functions — UEBA Detection Platform
-- =============================================================================

-- =============================================================================
-- fn_calculate_risk_decay()
-- Description: Menghitung decay factor untuk risk scoring.
--              Semakin lama sejak event, semakin kecil bobotnya.
-- Formula:     decay_factor = base_decay ^ hours_since
--              Default: 0.95 ^ hours_since
-- Returns:     DOUBLE PRECISION decay factor
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_calculate_risk_decay(
    p_event_time TIMESTAMPTZ,
    p_base_decay DOUBLE PRECISION DEFAULT 0.95
)
RETURNS DOUBLE PRECISION
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_hours_since DOUBLE PRECISION;
    v_decay_factor DOUBLE PRECISION;
BEGIN
    -- Hitung selisih jam dari event time sampai sekarang
    v_hours_since := EXTRACT(EPOCH FROM (NOW() - p_event_time)) / 3600.0;

    -- Jika event di masa depan atau 0 jam, decay = 1 (no decay)
    IF v_hours_since <= 0 THEN
        RETURN 1.0;
    END IF;

    -- Rumus exponential decay: base_decay ^ hours_since
    v_decay_factor := POWER(p_base_decay, v_hours_since);

    -- Floor minimal 0.01 agar tetap ada bobot minimal
    RETURN GREATEST(v_decay_factor, 0.01);
END;
$$;


-- =============================================================================
-- fn_get_entity_risk(entity_id)
-- Description: Mendapatkan current risk score untuk suatu entity.
--              Menghitung weighted average dari anomaly terbaru dengan decay.
--              Risk score dihitung dalam 7 hari terakhir.
-- Returns:     TABLE dengan risk_summary
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_get_entity_risk(p_entity_id INTEGER)
RETURNS TABLE (
    entity_id INTEGER,
    current_risk_score DOUBLE PRECISION,
    risk_level TEXT,
    total_anomalies BIGINT,
    highest_severity TEXT,
    last_anomaly_time TIMESTAMPTZ,
    top_anomaly_type TEXT,
    avg_decayed_score DOUBLE PRECISION
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_entity_exists BOOLEAN;
BEGIN
    -- Validasi entity exists
    SELECT EXISTS(SELECT 1 FROM entities WHERE id = p_entity_id) INTO v_entity_exists;

    IF NOT v_entity_exists THEN
        RAISE EXCEPTION 'Entity with id % not found', p_entity_id;
    END IF;

    RETURN QUERY
    WITH recent_anomalies AS (
        SELECT
            ad.id,
            ad.time,
            ad.score,
            ad.severity,
            ad.anomaly_type,
            sc.base_weight,
            sc.decay_factor AS config_decay,
            -- Severity multiplier: low=1, medium=2, high=3, critical=4
            CASE ad.severity
                WHEN 'low' THEN 1.0
                WHEN 'medium' THEN 2.0
                WHEN 'high' THEN 3.0
                WHEN 'critical' THEN 4.0
                ELSE 1.0
            END AS severity_multiplier,
            -- Decay factor berdasarkan waktu
            fn_calculate_risk_decay(ad.time, COALESCE(sc.decay_factor, 0.95)) AS decay
        FROM anomaly_detections ad
        LEFT JOIN scoring_config sc ON sc.anomaly_type = ad.anomaly_type
        WHERE ad.entity_id = p_entity_id
          AND ad.time > NOW() - INTERVAL '7 days'
          AND ad.status != 'resolved'
    ),
    weighted_scores AS (
        SELECT
            COUNT(*) AS total_anomalies,
            MAX(severity) AS highest_severity,
            MAX(time) AS last_anomaly_time,
            -- Weighted: (score * base_weight * severity_multiplier * decay)
            SUM(score * base_weight * severity_multiplier * decay) AS weighted_sum,
            SUM(base_weight * severity_multiplier * decay) AS weight_sum,
            -- Anomaly type with highest weighted score
            anomaly_type AS top_anomaly_type,
            -- Decayed average
            AVG(score * decay) AS avg_decayed_score
        FROM recent_anomalies
        GROUP BY anomaly_type
        ORDER BY SUM(score * base_weight * severity_multiplier * decay) DESC
        LIMIT 1
    )
    SELECT
        p_entity_id,
        -- Normalized risk score (0-100)
        LEAST(
            ROUND(
                COALESCE(weighted_sum / NULLIF(weight_sum, 0), 0.0)::numeric,
                2
            ),
            100.0
        )::DOUBLE PRECISION AS current_risk_score,
        -- Risk level mapping
        CASE
            WHEN COALESCE(weighted_sum / NULLIF(weight_sum, 0), 0.0) >= 70 THEN 'critical'
            WHEN COALESCE(weighted_sum / NULLIF(weight_sum, 0), 0.0) >= 50 THEN 'high'
            WHEN COALESCE(weighted_sum / NULLIF(weight_sum, 0), 0.0) >= 30 THEN 'medium'
            ELSE 'low'
        END AS risk_level,
        COALESCE(total_anomalies, 0)::BIGINT,
        COALESCE(highest_severity, 'none')::TEXT,
        last_anomaly_time,
        COALESCE(top_anomaly_type, 'none')::TEXT,
        ROUND(COALESCE(avg_decayed_score, 0.0)::numeric, 2)::DOUBLE PRECISION
    FROM weighted_scores;
END;
$$;


-- =============================================================================
-- fn_update_entity_risk()
-- Description: Trigger function untuk auto-update risk_score di entities table
--              setiap kali ada anomaly_detections baru.
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_update_entity_risk()
RETURNS TRIGGER
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    v_current_risk DOUBLE PRECISION;
    v_risk_level TEXT;
BEGIN
    -- Hitung risk score pake fn_get_entity_risk
    SELECT rs.current_risk_score, rs.risk_level
    INTO v_current_risk, v_risk_level
    FROM fn_get_entity_risk(NEW.entity_id) rs;

    -- Update entities table
    UPDATE entities
    SET
        risk_score = v_current_risk,
        risk_level = v_risk_level,
        last_seen = NOW()
    WHERE id = NEW.entity_id;

    RETURN NEW;
END;
$$;

-- Trigger on anomaly_detections insert
CREATE TRIGGER trg_after_anomaly_insert
    AFTER INSERT ON anomaly_detections
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_entity_risk();


-- =============================================================================
-- fn_generate_alert()
-- Description: Membuat alert record berdasarkan anomaly detection.
--              Alert severity mengikuti anomaly severity.
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_generate_alert(
    p_anomaly_id BIGINT,
    p_custom_message TEXT DEFAULT NULL
)
RETURNS anomaly_detections
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    v_alert anomaly_detections;
BEGIN
    -- Get the anomaly detection record
    SELECT * INTO v_alert
    FROM anomaly_detections
    WHERE id = p_anomaly_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Anomaly detection % not found', p_anomaly_id;
    END IF;

    -- Customize message if provided
    IF p_custom_message IS NOT NULL THEN
        v_alert.description := p_custom_message;
    END IF;

    RETURN v_alert;
END;
$$;
