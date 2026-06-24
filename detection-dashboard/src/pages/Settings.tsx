import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="max-w-2xl mx-auto">
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Settings className="w-12 h-12 text-ueba-text-muted mb-3" />
          <h2 className="text-lg font-semibold text-ueba-text-primary mb-1">Settings</h2>
          <p className="text-sm text-ueba-text-muted text-center">
            Dashboard settings and preferences will be available in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
