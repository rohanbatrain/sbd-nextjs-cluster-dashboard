'use client';

import React from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useClusterNodes } from '@/lib/api';
import { Server, MoreVertical, RefreshCw, Power, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';

export default function NodesPage() {
    const { nodes, isLoading, isError } = useClusterNodes();

    if (isLoading) return (
        <DashboardLayout>
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
        </DashboardLayout>
    );

    if (isError) return (
        <DashboardLayout>
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                Failed to load nodes.
            </div>
        </DashboardLayout>
    );

    return (
        <DashboardLayout>
            <div className="space-y-6">
                <div className="flex justify-between items-center">
                    <h1 className="text-2xl font-bold">Cluster Nodes</h1>
                    <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
                        Add Node
                    </button>
                </div>

                <div className="grid grid-cols-1 gap-4">
                    {nodes?.map((node: any) => (
                        <NodeCard key={node.node_id} node={node} />
                    ))}
                </div>
            </div>
        </DashboardLayout>
    );
}

function NodeCard({ node }: { node: any }) {
    const isHealthy = node.status === 'healthy';
    const isMaster = node.role === 'master';

    return (
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-6">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isHealthy ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                    <Server size={24} />
                </div>

                <div>
                    <div className="flex items-center gap-3">
                        <h3 className="font-bold text-lg">{node.node_id}</h3>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium uppercase border ${isMaster
                                ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                                : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            }`}>
                            {node.role}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium uppercase border ${isHealthy
                                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                : 'bg-red-500/10 text-red-400 border-red-500/20'
                            }`}>
                            {node.status}
                        </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
                        <span>{node.hostname}:{node.port}</span>
                        <span>•</span>
                        <span>Uptime: {formatUptime(node.health?.uptime_seconds || 0)}</span>
                        <span>•</span>
                        <span>Lag: {node.replication?.lag_seconds?.toFixed(3)}s</span>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-4">
                <div className="text-right mr-4">
                    <div className="text-sm text-gray-400">CPU Usage</div>
                    <div className="font-medium">{node.health?.cpu_usage || 0}%</div>
                </div>
                <div className="text-right mr-4">
                    <div className="text-sm text-gray-400">Memory</div>
                    <div className="font-medium">{node.health?.memory_usage || 0}%</div>
                </div>

                <div className="flex items-center gap-2">
                    {!isMaster && (
                        <button
                            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
                            title="Promote to Master"
                        >
                            <ArrowUpCircle size={20} />
                        </button>
                    )}
                    {isMaster && (
                        <button
                            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
                            title="Demote to Replica"
                        >
                            <ArrowDownCircle size={20} />
                        </button>
                    )}
                    <button
                        className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
                        title="Restart Node"
                    >
                        <RefreshCw size={20} />
                    </button>
                    <button
                        className="p-2 hover:bg-red-500/20 rounded-lg text-gray-400 hover:text-red-400 transition-colors"
                        title="Shutdown Node"
                    >
                        <Power size={20} />
                    </button>
                </div>
            </div>
        </div>
    );
}

function formatUptime(seconds: number) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}
