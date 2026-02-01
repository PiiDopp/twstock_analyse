const { createApp, ref, onMounted, nextTick } = Vue;

createApp({
    setup() {
        // --- 股票相關狀態 ---
        const stockId = ref('2330');
        const rtData = ref(null);         // 即時股票報價
        const hasData = ref(false);       // 是否顯示看板
        const chartType = ref('daily');   // 圖表類型: daily (日K) 或 intraday (分時)
        const cacheData = { daily: null, intraday: null };

        // --- 匯率相關狀態 ---
        const forexPair = ref('USDTWD');  // 預設匯率對
        const forexData = ref(null);      // 匯率查詢結果

        // --- 通用狀態 ---
        const loading = ref(false);
        const errorMsg = ref('');
        let chartInstance = null;

        // --- 生命週期與初始化 ---
        onMounted(() => {
            window.addEventListener('resize', () => {
                if (chartInstance) chartInstance.resize();
            });
            handleSearch();
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


        // 1. 股票查詢 (同時更新當前匯率)
        const handleSearch = async () => {
            if (!stockId.value) return;
            loading.value = true;
            errorMsg.value = '';
            
            // 清除舊股票快取
            cacheData.daily = null;
            cacheData.intraday = null;

            try {
                // 平行請求：即時股價、K線資料、以及當前指定的匯率
                const promises = [
                    axios.get(`http://127.0.0.1:8000/api/realtime/${stockId.value}`),
                    axios.get(`http://127.0.0.1:8000/api/${chartType.value === 'daily' ? 'stock' : 'intraday'}/${stockId.value}`),
                    axios.get(`http://127.0.0.1:8000/api/forex/${forexPair.value}`)
                ];

                const [rtRes, chartRes, forexRes] = await Promise.all(promises);

                rtData.value = rtRes.data;
                forexData.value = forexRes.data;
                hasData.value = true;

                // 儲存快取
                if (chartType.value === 'daily') cacheData.daily = chartRes.data;
                else cacheData.intraday = chartRes.data;

                await nextTick();
                initChart();

                // 渲染圖表
                if (chartType.value === 'daily') renderDailyChart(chartRes.data);
                else renderIntradayChart(chartRes.data);

            } catch (e) {
                console.error("查詢失敗:", e);
                errorMsg.value = '讀取失敗：' + (e.response?.data?.detail || e.message);
                if (chartInstance) chartInstance.clear();
            } finally {
                loading.value = false;
            }
        };

        // 2. 獨立匯率查詢
        const queryForex = async () => {
            if (!forexPair.value) return;
            try {
                const res = await axios.get(`http://127.0.0.1:8000/api/forex/${forexPair.value}`);
                forexData.value = res.data;
            } catch (e) {
                alert('匯率查詢失敗，請檢查格式（例如：JPYTWD 或 EURTWD）');
            }
        };

        // 3. 切換圖表類型 (日K / 分時)
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
                    const res = await axios.get(`http://127.0.0.1:8000/api/${endpoint}/${stockId.value}`);
                    cacheData[type] = res.data;
                    type === 'daily' ? renderDailyChart(res.data) : renderIntradayChart(res.data);
                }
            } catch (e) {
                errorMsg.value = '圖表切換失敗';
            } finally {
                loading.value = false;
            }
        };

        // --- ECharts 渲染函式 ---

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
            rtData, forexData, forexPair, queryForex,
            errorMsg, chartType, hasData, 
            getColor, getDiffColor, formatTime 
        };
    }
}).mount('#app');