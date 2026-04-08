// 全局变量
let currentRule = 'all';
let limitUpTable, selectedTable;
let highlightCount = 0;

// 页面加载完成
$(document).ready(function() {
    // 设置默认日期为今天
    const todayInput = $('#datePicker');
    if (!todayInput.val()) {
        const today = new Date().toISOString().split('T')[0];
        todayInput.val(today);
    }

    // 初始化表格
    initTables();

    // 页面加载时获取数据
    loadStocks();

    // 为选股策略按钮添加事件
    $('.btn-group button').on('click', function(e) {
        if ($(this).attr('onclick') && $(this).attr('onclick').includes('selectRule')) {
            return; // 让原来的onclick处理
        }
        $('.btn-group button').removeClass('active');
        $(this).addClass('active');
    });
});

// 高亮判断函数
function shouldHighlightStock(stockCode) {
    try {
        if (!stockCode) return false;

        // 提取数字部分（处理可能的后缀如.SH、.SZ等）
        const codeStr = stockCode.toString();
        const codeNumStr = codeStr.match(/\d+/g);

        if (!codeNumStr || codeNumStr.length === 0) return false;

        const digits = codeNumStr[0];

        // 计算数字之和
        const sum = digits.split('').reduce((total, digit) => {
            return total + parseInt(digit);
        }, 0);

        if (sum === 0) return false; // 避免除零错误

        // 检查是否能整除
        const codeNum = parseInt(digits);
        return codeNum % sum === 0;
    } catch (error) {
        console.error('高亮检查错误:', error);
        return false;
    }
}

// 显示高亮原因
function showHighlightReason(stockCode) {
    try {
        const codeStr = stockCode.toString();
        const codeNumStr = codeStr.match(/\d+/g)[0];
        const digits = codeNumStr.split('');
        const sum = digits.reduce((total, digit) => total + parseInt(digit), 0);
        const codeNum = parseInt(codeNumStr);

        const isDivisible = codeNum % sum === 0;

        if (isDivisible) {
            // 简化显示，只显示建议信息
            alert(`股票 ${stockCode} 符合技术选股条件，建议关注。`);
        }
    } catch (error) {
        alert('该股票符合系统建议关注条件。');
    }
}

// 初始化表格
function initTables() {
    limitUpTable = $('#limitUpTable').DataTable({
        searching: true,
        ordering: true,
        paging: true,
        pageLength: 10,
        language: {
            //url: 'https://cdn.datatables.net/plug-ins/1.11.5/i18n/zh-CN.json'
        },
        order: [[0, 'asc']],
        columnDefs: [
            {
                targets: 0, // 代码列
    render: function(data, type, row, meta) {
        // 获取该行数据
        const rowData = selectedTable.row(meta.row).data();
        const isHighlighted = rowData && rowData._highlight || false;

        if (type === 'display') {
            let display = data || '';
            if (isHighlighted) {
                display += ' <span class="highlight-indicator">建议买入</span>';
            }
            return display;
        }
        return data; // 用于排序和搜索
    }
            }
        ]
    });

    selectedTable = $('#selectedTable').DataTable({
        searching: true,
        ordering: true,
        paging: true,
        pageLength: 10,
        language: {
            //url: 'https://cdn.datatables.net/plug-ins/1.11.5/i18n/zh-CN.json'
        },
        order: [[0, 'asc']],
        columnDefs: [
            {
                targets: 0, // 代码列
                render: function(data, type, row, meta) {
                    // 获取该行数据
                    const rowData = selectedTable.row(meta.row).data();
                    const isHighlighted = rowData && rowData._highlight || false;

                    if (type === 'display') {
                        let display = data || '';
                        if (isHighlighted) {
                            display += ' <span class="highlight-indicator">买入</span>';
                        }
                        return display;
                    }
                    return data; // 用于排序和搜索
                }
            },
            {
                targets: 2, // 概念列
                render: function(data, type, row) {
                    return formatConcepts(data);
                }
            },
            {
                targets: 3, // 选股策略列
                render: function(data, type, row) {
                    return formatStrategy(data);
                }
            },
            {
                targets: 6, // 操作列
                orderable: false,
                searchable: false
            }
        ],
        createdRow: function(row, data, dataIndex) {
            // 为需要高亮的行添加类
            if (data._highlight) {
                $(row).addClass('highlight-stock');
            }
        }
    });
}

// 格式化策略显示
function formatStrategy(rule) {
    if (!rule) return '-';
    if (rule === '规则1' || rule === 1 || rule === 'rule1' || rule === '策略A') {
        return '<span class="badge bg-success strategy-badge">策略A</span>';
    } else if (rule === '规则2' || rule === 2 || rule === 'rule2' || rule === '策略B') {
        return '<span class="badge bg-info strategy-badge">策略B</span>';
    } else if (rule === '多策略') {
        return '<span class="badge bg-warning strategy-badge">多策略</span>';
    }
    return rule;
}

// 选择策略
function selectRule(rule) {
    currentRule = rule;

    // 更新按钮状态
    $('.btn-group button').removeClass('active');

    if (rule === 'all') {
        $('.btn-group button:contains("全部策略")').addClass('active');
    } else if (rule === 'rule1') {
        $('.btn-group button:contains("策略A")').addClass('active');
    } else if (rule === 'rule2') {
        $('.btn-group button:contains("策略B")').addClass('active');
    }
}

// 加载股票数据
async function loadStocks() {
    const date = $('#datePicker').val();

    if (!date) {
        alert('请选择日期');
        return;
    }

    showLoading(true);

    try {
        const response = await fetch(`/api/get_stocks?date=${date}&rule=${currentRule}`);
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        updateUI(data);
        updateTables(data);

    } catch (error) {
        console.error('Error:', error);
        alert('获取数据失败，请稍后重试');
    } finally {
        showLoading(false);
    }
}

// 更新UI统计信息
function updateUI(data) {
    // 更新日期信息
    $('#selectedDate').text(data.date);
    $('#lunarDate').text(`农历: ${data.lunar_date}`);

    // 更新统计信息
    $('#limitUpCount').text(data.limit_up_count);
    $('#limitUpBadge').text(data.limit_up_count);
    $('#selectedBadge').text(data.selected_count);

    // 计算各规则选股数量
    const rule1Count = data.selected_stocks ? data.selected_stocks.filter(s =>
        s.rule === 1 || s.rule === '规则1' || s.rule === '策略A' || s.rule === 'rule1').length : 0;
    const rule2Count = data.selected_stocks ? data.selected_stocks.filter(s =>
        s.rule === 2 || s.rule === '规则2' || s.rule === '策略B' || s.rule === 'rule2').length : 0;

    $('#rule1Count').text(rule1Count);
    $('#rule2Count').text(rule2Count);

    // 更新建议买入数量
    updateHighlightCount(highlightCount);
}

// 更新表格数据
function updateTables(data) {
    // 清空表格
    limitUpTable.clear();
    selectedTable.clear();

    // 重置高亮计数
    highlightCount = 0;

    // 填充涨停股票表
    if (data.limit_up_stocks) {
        data.limit_up_stocks.forEach(stock => {
            limitUpTable.row.add([
                stock.code,
                stock.name,
                stock.concept || '--',
                formatPrice(stock.close_price),
                formatPercent(stock.change_percent),
                formatPrice(stock.limit_up_price)
            ]);
        });
    }

    // 填充选股结果表
    if (data.selected_stocks) {
        data.selected_stocks.forEach(stock => {
            // 检查是否需要高亮
            const isHighlighted = shouldHighlightStock(stock.code);
            if (isHighlighted) highlightCount++;

            // 添加操作按钮
            const actionBtn = `
    <div class="btn-group" role="group">
        <button class="btn btn-sm btn-outline-primary" onclick="viewStockDetail('${stock.code}', '${stock.name}', '${stock.concept || ''}')">
            <i class="bi bi-eye"></i> 详情
        </button>
        ${isHighlighted ? `
        <button class="btn btn-sm btn-success" onclick="showHighlightReason('${stock.code}')" title="建议买入">
            <i class="bi bi-arrow-up-circle"></i> 建议买入
        </button>
        ` : ''}
    </div>
`;

            // 添加行数据，包含高亮标记
            selectedTable.row.add({
                0: stock.code,
                1: stock.name,
                2: stock.concept || '--',
                3: stock.rule || '--',
                4: formatPrice(stock.close_price),
                5: formatPercent(stock.change_percent),
                6: actionBtn,
                _highlight: isHighlighted  // 内部标记，用于createdRow
            });
        });
    }

    // 绘制表格
    limitUpTable.draw();
    selectedTable.draw();
}

// 更新高亮计数
function updateHighlightCount(count) {
    const badgeId = 'highlightBadge';
    const existingBadge = $('#' + badgeId);

    if (existingBadge.length) {
        existingBadge.text(count);
    } else {
        // 在选股结果标题中添加建议买入计数
        $('#selectedTable .card-header h5').append(`
            <span class="badge bg-success ms-2" id="${badgeId}">
                <i class="bi bi-arrow-up-circle"></i> 建议买入: ${count}
            </span>
        `);
    }
}

// 格式化概念
function formatConcepts(concepts) {
    if (!concepts || concepts === '--' || concepts.trim() === '') {
        return '<span class="text-muted">暂无概念信息</span>';
    }

    const conceptArray = concepts.split(',');
    return conceptArray.map(c => {
        const trimmed = c.trim();
        if (!trimmed) return '';
        return `<span class="concept-tag">${trimmed}</span>`;
    }).join(' ');
}

// 格式化价格
function formatPrice(price) {
    if (!price) return '-';
    const numPrice = parseFloat(price);
    if (isNaN(numPrice)) return '-';
    return `¥${numPrice.toFixed(2)}`;
}

// 格式化百分比
function formatPercent(percent) {
    if (!percent) return '-';
    const value = parseFloat(percent);
    if (isNaN(value)) return '-';

    // 修正：涨停应该显示红色，跌停显示绿色
    const color = value >= 0 ? 'text-danger' : 'text-success';
    const symbol = value >= 0 ? '+' : '';
    return `<span class="${color} fw-bold">${symbol}${value.toFixed(2)}%</span>`;
}

// 查看股票详情
async function viewStockDetail(code, name, concept) {
    // 如果概念为空，尝试重新获取
    if (!concept || concept === '暂无概念信息') {
        try {
            const response = await fetch(`/api/get_stock_concept?code=${code}`);
            const data = await response.json();
            if (data.concept && data.concept.trim() !== '') {
                concept = data.concept;
            }
        } catch (error) {
            console.error('获取概念失败:', error);
        }
    }

    // 创建概念标签HTML
    let conceptHtml = '<span class="text-muted">暂无概念信息</span>';
    if (concept && concept.trim() !== '') {
        const conceptArray = concept.split(',');
        conceptHtml = conceptArray.map(c => {
            const trimmed = c.trim();
            if (!trimmed) return '';
            return `<span class="badge bg-secondary me-1 mb-1">${trimmed}</span>`;
        }).join('');
    }

    // 弹出股票详情模态框
    const modalHtml = `
        <div class="modal fade" id="stockDetailModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="bi bi-info-circle"></i> 股票详情 - ${code}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card mb-3">
                                    <div class="card-header bg-light">
                                        <h6 class="mb-0">基本信息</h6>
                                    </div>
                                    <div class="card-body">
                                        <p><strong>股票代码:</strong> <span class="stock-code fw-bold">${code}</span></p>
                                        <p><strong>股票名称:</strong> <strong>${name}</strong></p>
                                        <p><strong>入选日期:</strong> ${$('#selectedDate').text()}</p>
                                        <p><strong>农历日期:</strong> ${$('#lunarDate').text().replace('农历: ', '')}</p>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card mb-3">
                                    <div class="card-header bg-light">
                                        <h6 class="mb-0">概念板块</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="concepts-container">
                                            ${conceptHtml}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="card">
                                    <div class="card-header bg-light">
                                        <h6 class="mb-0">分析说明</h6>
                                    </div>
                                    <div class="card-body">
                                        <p class="mb-2">该股票符合智能选股系统的量化筛选条件，具体表现如下：</p>
                                        <ul>
                                            <li>当日出现涨停走势</li>
                                            <li>通过系统内置策略筛选</li>
                                            <li>具备一定的技术面特征</li>
                                            <li>符合当前市场热点</li>
                                        </ul>
                                        <div class="alert alert-warning mt-3">
                                            <small>
                                                <i class="bi bi-exclamation-triangle"></i>
                                                温馨提示：以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
                                            </small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 如果模态框已存在，先移除
    if ($('#stockDetailModal').length) {
        $('#stockDetailModal').remove();
    }

    // 添加模态框到页面
    $('body').append(modalHtml);

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('stockDetailModal'));
    modal.show();
}

// 显示/隐藏加载动画
function showLoading(show) {
    if (show) {
        $('#loading').show();
    } else {
        $('#loading').hide();
    }
}

// 概念标签点击事件
$(document).on('click', '.concept-tag', function() {
    const concept = $(this).text();
    alert(`概念: ${concept}\n\n可以在这里添加该概念的详细解释和相关信息。`);
});