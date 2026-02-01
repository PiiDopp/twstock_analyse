const { createApp, ref, onMounted, nextTick } = Vue;

createApp({
    setup() {
        const API_BASE = 'http://127.0.0.1:8000'; 

        // --- 股票狀態 ---
        const stockId = ref('2330');
        const rtData = ref(null);         
        const hasData = ref(false);       
        const chartType = ref('daily');   
        const cacheData = { daily: null, intraday: null };
        const loading = ref(false);
        const errorMsg = ref('');
        let chartInstance = null;

        // --- 排行榜狀態 (新增) ---
        const rankList = ref([]);
        const rankType = ref('up'); // 'up' or 'down'
        const rankLoading = ref(false);

        // --- 匯率狀態 ---
        const currencyFrom = ref('USD');
        const currencyTo = ref('TWD');
        const forexData = ref(null);      
        const forexLoading = ref(false);
        const currencyOptions = [
            { code: 'TWD', name: '新台幣' }, { code: 'USD', name: '美金' },
            { code: 'JPY', name: '日圓' }, { code: 'EUR', name: '歐元' },
            { code: 'CNY', name: '人民幣' }, { code: 'HKD', name: '港幣' },
            { code: 'AUD', name: '澳幣' }, { code: 'BTC', name: '比特幣' }
        ];

        onMounted(() => {
            window.addEventListener('resize', () => {
                if (chartInstance) chartInstance.resize();
            });
            handleSearch();
            queryForex();
            fetchRank('up'); // 預設載入漲幅排行
        });

        const initChart = () => {
            const chartDom = document.getElementById('chart');
            if (chartDom && !chartInstance) {
                chartInstance = echarts.init(chartDom);
            }
        };

        const getColor = (val, refVal) => {
            if (val == null || refVal == null) return 'text-black';
            return val > refVal ? 'text-red' : (val < refVal ? 'text-green' : 'text-black');
        };

        const getDiffColor = (val) => {
            if (val == null) return 'text-black';
            return val > 0 ? 'text-red' : (val < 0 ? 'text-green' : 'text-black');
        };

        const formatTime = (ts) => {
            if (!ts) return '-';
            const date = ts > 10000000000 ? new Date(ts) : new Date(ts * 1000);
            return date.toLocaleTimeString('zh-TW', { hour12: false });
        };

        // --- 新增：獲取排行榜 ---
        const fetchRank = async (type) => {
            rankType.value = type;
            rankLoading.value = true;
            try {
                const res = await axios.get(`${API_BASE}/api/rank/${type}`);
                rankList.value = res.data;
            } catch (e) {
                console.error("排行讀取失敗", e);
            } finally {
                rankLoading.value = false;
            }
        };

        // --- 新增：點擊清單選擇股票 ---
        const selectStock = (code) => {
            stockId.value = code;
            handleSearch(); // 觸發搜尋
        };

        // 1. 股票查詢
        const handleSearch = async () => {
            if (!stockId.value) return;
            loading.value = true;
            errorMsg.value = '';
            
            cacheData.daily = null;
            cacheData.intraday = null;

            try {
                const promises = [
                    axios.get(`${API_BASE}/api/realtime/${stockId.value}`),
                    axios.get(`${API_BASE}/api/${chartType.value === 'daily' ? 'stock' : 'intraday'}/${stockId.value}`)
                ];

                const [rtRes, chartRes] = await Promise.all(promises);

                rtData.value = rtRes.data;
                hasData.value = true;

                if (chartType.value === 'daily') cacheData.daily = chartRes.data;
                else cacheData.intraday = chartRes.data;

                await nextTick();
                initChart();

                if (chartType.value === 'daily') renderDailyChart(chartRes.data);
                else renderIntradayChart(chartRes.data);

            } catch (e) {
                console.error("股票查詢失敗:", e);
                errorMsg.value = '讀取失敗：' + (e.response?.data?.detail || e.message);
                if (chartInstance) chartInstance.clear();
            } finally {
                loading.value = false;
            }
        };

        // 2. 匯率查詢
        const queryForex = async () => {
            if (!currencyFrom.value || !currencyTo.value) return;
            if (currencyFrom.value === currencyTo.value) return;

            forexLoading.value = true;
            const pair = `${currencyFrom.value}${currencyTo.value}`;

            try {
                const res = await axios.get(`${API_BASE}/api/forex/${pair}`);
                forexData.value = res.data;
            } catch (e) {
                console.error("匯率查詢失敗", e);
                forexData.value = null;
            } finally {
                forexLoading.value = false;
            }
        };

        // 3. 切換圖表
        const switchTab = async (type) => {
            if (chartType.value === type) return;
            chartType.value = type;
            loading.value = true;
            await nextTick();
            initChart();
            try {
                if (cacheData[type]) {
                    type === 'daily' ? renderDailyChart(cacheData[type]) : renderIntradayChart(cacheData[type]);
                } else {
                    const endpoint = type === 'daily' ? 'stock' : 'intraday';
                    const res = await axios.get(`${API_BASE}/api/${endpoint}/${stockId.value}`);
                    cacheData[type] = res.data;
                    type === 'daily' ? renderDailyChart(res.data) : renderIntradayChart(res.data);
                }
            } catch (e) { errorMsg.value = '圖表切換失敗'; } 
            finally { loading.value = false; }
        };

        // --- ECharts 渲染 (保持不變) ---
        const renderDailyChart = (data) => {
            chartInstance.clear();
            const option = {
                animation: false,
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                legend: { data: ['日K', 'MA5', 'MA20', 'MA60'], top: 10 },
                grid: { left: '8%', right: '4%', bottom: '15%', top: '15%' },
                xAxis: { type: 'category', data: data.dates, scale: true },
                yAxis: { scale: true, splitLine: { show: true, lineStyle: { color: '#eee' } } },
                dataZoom: [{ type: 'inside', start: 70, end: 100 }, { show: true, type: 'slider', top: '92%' }],
                series: [
                    {
                        name: '日K',
                        type: 'candlestick',
                        data: data.values,
                        itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' }
                    },
                    { name: 'MA5', type: 'line', data: data.ma5, smooth: true, lineStyle: { width: 1, color: '#f39c12' }, showSymbol: false },
                    { name: 'MA20', type: 'line', data: data.ma20, smooth: true, lineStyle: { width: 1, color: '#9b59b6' }, showSymbol: false },
                    { name: 'MA60', type: 'line', data: data.ma60, smooth: true, lineStyle: { width: 2, color: '#2ecc71' }, showSymbol: false }
                ]
            };
            chartInstance.setOption(option);
        };

        const renderIntradayChart = (data) => {
            chartInstance.clear();
            const lastPrice = data.prices[data.prices.length - 1];
            const color = lastPrice >= data.ref_price ? '#ef232a' : '#14b143';
            
            const option = {
                animation: false,
                tooltip: { trigger: 'axis' },
                grid: { left: '8%', right: '4%', bottom: '10%', top: '15%' },
                xAxis: { type: 'category', data: data.times, axisLabel: { interval: 59 } },
                yAxis: { 
                    scale: true,
                    min: (val) => Math.min(val.min, data.ref_price) * 0.995,
                    max: (val) => Math.max(val.max, data.ref_price) * 1.005
                },
                series: [{
                    name: '價格',
                    type: 'line',
                    data: data.prices,
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { color: color, width: 2 },
                    areaStyle: { opacity: 0.1, color: color },
                    markLine: {
                        symbol: ['none', 'none'],
                        data: [{ yAxis: data.ref_price, label: { position: 'start', formatter: '昨收' } }],
                        lineStyle: { type: 'dashed', color: 'gray' }
                    }
                }]
            };
            chartInstance.setOption(option);
        };

        return { 
            stockId, handleSearch, switchTab, loading, 
            rtData, errorMsg, chartType, hasData, 
            currencyFrom, currencyTo, currencyOptions, forexData, queryForex, forexLoading,
            rankList, rankType, rankLoading, fetchRank, selectStock,
            getColor, getDiffColor, formatTime 
        };
    }
}).mount('#app');