import { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight, Shield, AlertTriangle } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { Badge } from '@/components/ui/Badge';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { getRules, createRule, updateRule, deleteRule, type Rule, type RuleCreatePayload, type RuleUpdatePayload } from '@/lib/api';

const SEVERITY_COLORS: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'info',
  low: 'success',
};

const OPERATORS = [
  { value: 'equals', label: 'Equals' },
  { value: 'not_equals', label: 'Not Equals' },
  { value: 'contains', label: 'Contains' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
  { value: 'in_list', label: 'In List' },
  { value: 'not_in_list', label: 'Not In List' },
  { value: 'matches_regex', label: 'Matches Regex' },
];

const FIELDS = [
  { value: 'event_type', label: 'Event Type' },
  { value: 'source', label: 'Source' },
  { value: 'source_ip', label: 'Source IP' },
  { value: 'log_level', label: 'Log Level' },
  { value: 'risk_score', label: 'Risk Score' },
  { value: 'risk_level', label: 'Risk Level' },
  { value: 'is_anomaly', label: 'Is Anomaly' },
  { value: 'entity', label: 'Entity' },
];

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <Shield className="w-16 h-16 text-ueba-text-muted mb-4" />
      <h3 className="text-lg font-semibold text-ueba-text-primary mb-1">No Rules Yet</h3>
      <p className="text-sm text-ueba-text-muted mb-4 text-center max-w-md">
        Create custom detection rules to automatically generate alerts when conditions are met.
      </p>
      <Button onClick={onCreate}>
        <Plus className="w-4 h-4 mr-2" /> Create Your First Rule
      </Button>
    </div>
  );
}

function ConditionRow({ condition, index, onChange, onRemove }: {
  condition: any;
  index: number;
  onChange: (idx: number, data: any) => void;
  onRemove: (idx: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 p-2 bg-ueba-bg-deep rounded border border-ueba-border">
      <span className="text-xs text-ueba-text-muted w-4">{index + 1}</span>
      <select
        value={condition.field || ''}
        onChange={(e) => onChange(index, { ...condition, field: e.target.value })}
        className="bg-ueba-card border border-ueba-border rounded px-2 py-1 text-xs text-ueba-text-primary w-32"
      >
        <option value="">Select field</option>
        {FIELDS.map((f) => (
          <option key={f.value} value={f.value}>{f.label}</option>
        ))}
      </select>
      <select
        value={condition.operator || 'equals'}
        onChange={(e) => onChange(index, { ...condition, operator: e.target.value })}
        className="bg-ueba-card border border-ueba-border rounded px-2 py-1 text-xs text-ueba-text-primary w-28"
      >
        {OPERATORS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <input
        value={condition.value ?? ''}
        onChange={(e) => onChange(index, { ...condition, value: e.target.value })}
        placeholder="Value"
        className="bg-ueba-card border border-ueba-border rounded px-2 py-1 text-xs text-ueba-text-primary flex-1 min-w-[100px]"
      />
      <button onClick={() => onRemove(index)} className="text-ueba-text-muted hover:text-ueba-accent-red p-1">
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function RuleFormModal({ rule, onClose, onSave }: {
  rule: Rule | null;
  onClose: () => void;
  onSave: (data: RuleCreatePayload) => Promise<void>;
}) {
  const [name, setName] = useState(rule?.name || '');
  const [description, setDescription] = useState(rule?.description || '');
  const [severity, setSeverity] = useState(rule?.action?.severity || 'medium');
  const [alertTitle, setAlertTitle] = useState(rule?.action?.title || '');
  const [alertDesc, setAlertDesc] = useState(rule?.action?.description || '');
  const [enabled, setEnabled] = useState(rule?.enabled ?? true);
  const [priority, setPriority] = useState(rule?.priority ?? 5);
  const [conditions, setConditions] = useState<any[]>(
    rule?.conditions?.conditions?.filter((c: any) => c.field) || [{ field: '', operator: 'equals', value: '' }]
  );
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        name,
        description: description || undefined,
        conditions: { logic: 'AND', conditions: conditions.filter((c) => c.field) },
        action: {
          type: 'create_alert',
          severity: severity as any,
          title: alertTitle,
          description: alertDesc,
        },
        enabled,
        priority,
      });
    } finally {
      setSaving(false);
    }
  };

  const updateCondition = (idx: number, data: any) => {
    const updated = [...conditions];
    updated[idx] = data;
    setConditions(updated);
  };

  const removeCondition = (idx: number) => {
    setConditions(conditions.filter((_, i) => i !== idx));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-ueba-bg border border-ueba-border rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4">
        <div className="flex items-center justify-between p-4 border-b border-ueba-border">
          <h2 className="text-lg font-bold text-ueba-text-primary">
            {rule ? 'Edit Rule' : 'Create Rule'}
          </h2>
          <button onClick={onClose} className="text-ueba-text-muted hover:text-ueba-text-primary">&times;</button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="block text-xs text-ueba-text-muted mb-1">Rule Name *</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Suspicious Login Detection" />
          </div>

          <div>
            <label className="block text-xs text-ueba-text-muted mb-1">Description</label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe what this rule detects" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-ueba-text-muted">Conditions (ALL must match)</label>
              <button
                onClick={() => setConditions([...conditions, { field: '', operator: 'equals', value: '' }])}
                className="text-xs text-ueba-accent-blue hover:underline"
              >
                + Add Condition
              </button>
            </div>
            <div className="space-y-2">
              {conditions.map((cond, i) => (
                <ConditionRow
                  key={i}
                  condition={cond}
                  index={i}
                  onChange={updateCondition}
                  onRemove={removeCondition}
                />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-ueba-text-muted mb-1">Alert Severity</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as any)}
                className="bg-ueba-card border border-ueba-border rounded px-3 py-2 text-sm text-ueba-text-primary w-full"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-ueba-text-muted mb-1">Priority</label>
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="bg-ueba-card border border-ueba-border rounded px-3 py-2 text-sm text-ueba-text-primary w-full"
                min={0}
                max={100}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-ueba-text-muted mb-1">Alert Title</label>
            <Input value={alertTitle} onChange={(e) => setAlertTitle(e.target.value)} placeholder="Alert title shown in Alerts page" />
          </div>

          <div>
            <label className="block text-xs text-ueba-text-muted mb-1">Alert Description</label>
            <Input value={alertDesc} onChange={(e) => setAlertDesc(e.target.value)} placeholder="Description of the alert" />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-ueba-border"
            />
            <label className="text-sm text-ueba-text-primary">Enable rule immediately</label>
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-ueba-border">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={!name || saving}>
            {saving ? 'Saving...' : rule ? 'Update Rule' : 'Create Rule'}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getRules({ page, limit: 20 });
      setRules(res.data);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch rules');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const handleCreate = async (data: RuleCreatePayload) => {
    await createRule(data);
    setShowForm(false);
    fetchRules();
  };

  const handleUpdate = async (data: RuleUpdatePayload) => {
    if (!editingRule) return;
    await updateRule(editingRule.id, data);
    setEditingRule(null);
    setShowForm(false);
    fetchRules();
  };

  const handleToggle = async (rule: Rule) => {
    await updateRule(rule.id, { enabled: !rule.enabled });
    fetchRules();
  };

  const handleDelete = async (id: number) => {
    await deleteRule(id);
    setDeletingId(null);
    fetchRules();
  };

  const openEdit = (rule: Rule) => {
    setEditingRule(rule);
    setShowForm(true);
  };

  if (loading && !rules.length) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-ueba-accent-blue" />
          <h1 className="text-lg font-bold text-ueba-text-primary">Custom Rules</h1>
          <Badge variant="info">{total} rules</Badge>
        </div>
        <Button onClick={() => { setEditingRule(null); setShowForm(true); }}>
          <Plus className="w-4 h-4 mr-2" /> New Rule
        </Button>
      </div>

      {error && (
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-ueba-accent-red">{error}</p>
          </CardContent>
        </Card>
      )}

      {rules.length === 0 && !loading ? (
        <EmptyState onCreate={() => { setEditingRule(null); setShowForm(true); }} />
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <Card key={rule.id}>
              <CardContent className="py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-semibold text-ueba-text-primary">{rule.name}</h3>
                      <Badge variant={SEVERITY_COLORS[rule.action?.severity] || 'info'}>
                        {rule.action?.severity || 'unknown'}
                      </Badge>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${rule.enabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-400'}`}>
                        {rule.enabled ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                    {rule.description && (
                      <p className="text-xs text-ueba-text-muted mb-2">{rule.description}</p>
                    )}
                    {rule.conditions?.conditions?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {rule.conditions.conditions.filter((c: any) => c.field).map((cond: any, i: number) => (
                          <span key={i} className="text-[10px] bg-ueba-bg-deep border border-ueba-border rounded px-1.5 py-0.5 text-ueba-text-secondary font-mono">
                            {cond.field} {cond.operator} {String(cond.value)}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="text-[10px] text-ueba-text-muted mt-2">
                      Created: {new Date(rule.created_at).toLocaleDateString()} | Priority: {rule.priority}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleToggle(rule)}
                      className="p-2 rounded hover:bg-ueba-cardhover text-ueba-text-muted hover:text-ueba-text-primary"
                      title={rule.enabled ? 'Disable' : 'Enable'}
                    >
                      {rule.enabled ? <ToggleRight className="w-4 h-4 text-emerald-400" /> : <ToggleLeft className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => openEdit(rule)}
                      className="p-2 rounded hover:bg-ueba-cardhover text-ueba-text-muted hover:text-ueba-text-primary"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setDeletingId(rule.id)}
                      className="p-2 rounded hover:bg-ueba-cardhover text-ueba-text-muted hover:text-ueba-accent-red"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {total > 20 && (
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(total / 20)}
          onPageChange={setPage}
        />
      )}

      {/* Create/Edit Modal */}
      {showForm && (
        <RuleFormModal
          rule={editingRule}
          onClose={() => { setShowForm(false); setEditingRule(null); }}
          onSave={editingRule ? handleUpdate : handleCreate}
        />
      )}

      {/* Delete Confirmation */}
      {deletingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-ueba-bg border border-ueba-border rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-ueba-accent-red" />
              <h3 className="text-lg font-bold text-ueba-text-primary">Delete Rule?</h3>
            </div>
            <p className="text-sm text-ueba-text-muted mb-6">
              This action cannot be undone. The rule will stop evaluating immediately.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeletingId(null)}>Cancel</Button>
              <Button onClick={() => handleDelete(deletingId)}>Delete</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
