import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import lodash from 'lodash';
import moment from 'moment';
const { promisify } = require('util');
const fs = require('fs');

const greetUser = (name) => {
    return `Hello, ${name}!`;
};

function calculateSum(a, b) {
    return a + b;
}

async function fetchUserData(userId) {
    try {
        const response = await axios.get(`/api/users/${userId}`);
        return response.data;
    } catch (error) {
        console.error('Error fetching user data:', error);
        throw error;
    }
}

const processArray = function(arr) {
    return arr
        .filter(item => item.active)
        .map(item => ({
            ...item,
            processedAt: moment().toISOString()
        }));
};

const createValidator = (rules) => {
    return (data) => {
        return rules.every(rule => rule(data));
    };
};

function UserProfile({ userId, onUpdate }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const loadUser = useCallback(async () => {
        setLoading(true);
        try {
            const userData = await fetchUserData(userId);
            setUser(userData);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [userId]);

    useEffect(() => {
        loadUser();
    }, [loadUser]);

    const handleUpdate = useCallback((updates) => {
        setUser(prev => ({ ...prev, ...updates }));
        onUpdate(updates);
    }, [onUpdate]);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;

    return (
        <div className="user-profile">
            <h2>{user?.name}</h2>
            <p>{user?.email}</p>
            <button onClick={() => handleUpdate({ lastViewed: new Date() })}>
                Update Last Viewed
            </button>
        </div>
    );
}

const APIService = {
    baseURL: '/api',

    get: async function(endpoint) {
        const url = `${this.baseURL}${endpoint}`;
        return await axios.get(url);
    },

    post(endpoint, data) {
        const url = `${this.baseURL}${endpoint}`;
        return axios.post(url, data);
    },

    delete(endpoint) {
        return axios.delete(`${this.baseURL}${endpoint}`);
    }
};

class DataManager {
    constructor(config) {
        this.config = config;
        this.cache = new Map();
    }

    async getData(key) {
        if (this.cache.has(key)) {
            return this.cache.get(key);
        }

        const data = await this.fetchData(key);
        this.cache.set(key, data);
        return data;
    }

    async fetchData(key) {
        const response = await APIService.get(`/data/${key}`);
        return response.data;
    }

    clearCache() {
        this.cache.clear();
    }

    static createDefault() {
        return new DataManager({
            cacheSize: 100,
            ttl: 3600000
        });
    }
}

function* numberGenerator(start, end) {
    for (let i = start; i <= end; i++) {
        yield i;
    }
}

(function() {
    console.log('IIFE executed');
})();

export default UserProfile;
export { greetUser, calculateSum, fetchUserData, DataManager };

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        UserProfile,
        greetUser,
        calculateSum,
        fetchUserData,
        APIService,
        DataManager
    };
}