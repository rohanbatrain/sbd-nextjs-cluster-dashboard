'use client';

import React from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';

export default function SettingsPage() {
    return (
        <DashboardLayout>
            <div className="space-y-6">
                <h1 className="text-2xl font-bold">Cluster Settings</h1>

                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
                    <h2 className="text-lg font-medium mb-4">General Configuration</h2>
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Cluster Name</label>
                                <input
                                    type="text"
                                    value="production-cluster-01"
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                    readOnly
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Topology Type</label>
                                <select className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500">
                                    <option>Master-Slave</option>
                                    <option>Master-Master</option>
                                    <option>Multi-Master</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
                    <h2 className="text-lg font-medium mb-4">Load Balancing</h2>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Algorithm</label>
                            <select className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500">
                                <option>Round Robin</option>
                                <option>Least Connections</option>
                                <option>Weighted Round Robin</option>
                                <option>IP Hash</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <input type="checkbox" id="sticky" className="rounded bg-gray-900 border-gray-700 text-blue-500" defaultChecked />
                            <label htmlFor="sticky" className="text-sm text-gray-300">Enable Sticky Sessions</label>
                        </div>
                    </div>
                </div>

                <div className="flex justify-end gap-4">
                    <button className="px-4 py-2 text-gray-400 hover:text-white transition-colors">Cancel</button>
                    <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors">
                        Save Changes
                    </button>
                </div>
            </div>
        </DashboardLayout>
    );
}
