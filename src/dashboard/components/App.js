import React, { useState, useEffect } from 'react';
import StationMetrics from './StationMetrics';
import AlertPanel from './AlertPanel';
import QueueAnalytics from './QueueAnalytics';
import InventoryOverview from './InventoryOverview';

const App = () => {
    const [realTimeData, setRealTimeData] = useState({
        stations: {},
        alerts: [],
        queueMetrics: {},
        inventory: {}
    });

    // WebSocket connection for real-time updates
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8766');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setRealTimeData(prev => updateDashboardState(prev, data));
        };
        return () => ws.close();
    }, []);

    return (
        <div className="dashboard">
            <div className="header">
                <h1>Project Sentinel - Retail Intelligence Dashboard</h1>
                <div className="timestamp">Last Updated: {new Date().toLocaleTimeString()}</div>
            </div>

            <div className="main-grid">
                <StationMetrics data={realTimeData.stations} />
                <AlertPanel alerts={realTimeData.alerts} />
                <QueueAnalytics metrics={realTimeData.queueMetrics} />
                <InventoryOverview inventory={realTimeData.inventory} />
            </div>
        </div>
    );
};