// File: src/dashboard/components/QueueAnalytics.js
import React from 'react';

const QueueAnalytics = ({ metrics }) => {
    const calculateOptimalStaffing = (customerCount) => {
        // @algorithm OptimalStaffing | Calculate staff needed based on customer-to-kiosk ratio
        const targetRatio = 6; // 6 customers per kiosk
        return Math.ceil(customerCount / targetRatio);
    };

    const getQueueHealth = (dwellTime, customerCount) => {
        if (dwellTime > 600 || customerCount > 8) return 'critical';
        if (dwellTime > 300 || customerCount > 5) return 'warning';
        return 'healthy';
    };

    return (
        <div className="queue-analytics">
            <h3>Queue Management</h3>
            {Object.entries(metrics).map(([stationId, data]) => (
                <div key={stationId} className={`queue-station ${getQueueHealth(data.avgDwellTime, data.customerCount)}`}>
                    <h4>Station {stationId}</h4>
                    <p>Customers: {data.customerCount}</p>
                    <p>Avg Wait: {Math.round(data.avgDwellTime / 60)} minutes</p>
                    <p>Recommended Staff: {calculateOptimalStaffing(data.customerCount)}</p>
                </div>
            ))}
        </div>
    );
};