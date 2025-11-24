'use client';

import React from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useActiveAlerts, apiClient, Alert } from '@/lib/api';
import { AlertTriangle, AlertCircle, Info, XCircle, Check, Clock } from 'lucide-react';

const severityConfig = {
    critical: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
    error: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    warning: { icon: AlertCircle, color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
    info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
};

export default function AlertsPage() {
    const { alerts, isLoading, isError, refetch } = useActiveAlerts();
    const [resolving, setResolving] = React.useState<string | null>(null);

    const handleResolve = async (alertId: string) => {
        setResolving(alertId);
        try {
            await apiClient.resolveAlert(alertId);
            await refetch();
        } catch (error) {
            console.error('Failed to resolve alert:', error);
        } finally {
            setResolving(null);
        }
    };

    if (isLoading) {
        return (
            <DashboardLayout>
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                </div>
            </DashboardLayout>
        );
    }

    if (isError) {
        return (
            <DashboardLayout>
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                    Failed to load alerts. Is the backend running?
                </div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout>
            <div className="space-y-6">
                {/* Header */}
                <div>
                    <h2 className="text-2xl font-bold">Cluster Alerts</h2>
                    <p className="text-gray-400 mt-1">
                        Real-time monitoring and alerting for cluster health
                    </p>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <StatCard
                        title="Total Alerts"
                        value={alerts.length}
                        color="text-blue-400"
                    />
                    <StatCard
                        title="Critical"
                        value={alerts.filter(a => a.severity === 'critical').length}
                        color="text-red-400"
                    />
                    <StatCard
                        title="Warning"
                        value={alerts.filter(a => a.severity === 'warning').length}
                        color="text-yellow-400"
                    />
                    <StatCard
                        title="Info"
                        value={alerts.filter(a => a.severity === 'info').length}
                        color="text-blue-400"
                    />
                </div>

                {/* Active Alerts */}
                <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                    <div className="p-6 border-b border-gray-700">
                        <h3 className="text-lg font-medium">Active Alerts</h3>
                    </div>

                    {alerts.length === 0 ? (
                        <div className="p-12 text-center">
                            <Check className="mx-auto text-green-400 mb-4" size={48} />
                            <h4 className="text-lg font-medium text-gray-300 mb-2">All Clear!</h4>
                            <p className="text-gray-400">No active alerts at this time.</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-gray-700">
                            {alerts.map((alert) => (
                                <AlertCard
                                    key={alert.alert_id}
                                    alert={alert}
                                    onResolve={handleResolve}
                                    isResolving={resolving === alert.alert_id}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
}

function StatCard({ title, value, color }: { title: string; value: number; color: string }) {
    return (
        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <p className="text-gray-400 text-sm">{title}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
        </div>
    );
}

function AlertCard({ alert, onResolve, isResolving }: {
    alert: Alert;
    onResolve: (id: string) => void;
    isResolving: boolean;
}) {
    const config = severityConfig[alert.severity];
    const Icon = config.icon;
    const timeAgo = getTimeAgo(new Date(alert.timestamp));

    return (
        <div className={`p-6 flex items-start gap-4 ${config.bg}`}>
            <Icon className={`${config.color} shrink-0 mt-1`} size={24} />
            <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                            <h4 className={`font-medium ${config.color}`}>{alert.title}</h4>
                            <span className={`text-xs px-2 py-0.5 rounded ${config.border} border`}>
                                {alert.severity.toUpperCase()}
                            </span>
                        </div>
                        <p className="text-sm text-gray-300 mt-1">{alert.message}</p>
                        {alert.node_id && (
                            <p className="text-xs text-gray-500 mt-2">
                                Node: <code className="text-gray-400">{alert.node_id}</code>
                            </p>
                        )}
                        <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
                            <Clock size={12} />
                            <span>{timeAgo}</span>
                        </div>
                    </div>
                    <button
                        onClick={() => onResolve(alert.alert_id)}
                        disabled={isResolving}
                        className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded border border-gray-600 transition-colors disabled:opacity-50"
                    >
                        {isResolving ? 'Resolving...' : 'Resolve'}
                    </button>
                </div>
            </div>
        </div>
    );
}

function getTimeAgo(date: Date): string {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}
