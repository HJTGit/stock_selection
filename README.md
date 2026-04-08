# 涨停股票选股系统

根据涨停股票数据，按照指定规则筛选符合条件的股票。

## 功能特性

- 获取每日涨停股票数据（来源：akshare）
- 规则1：股票代码除以下一交易日（月份+日期）的余数为0
- 规则2：股票代码除以农历（月份+日期）的余数为0
- 历史数据存储于 MySQL，重复查询直接从数据库读取
- 收盘后自动保存当日数据（每个交易日 15:35 执行）

## 技术栈

- Flask + SQLAlchemy
- MySQL 数据库
- akshare 数据源
- APScheduler 定时任务

## 配置

数据库配置位于 `app.py` 第 18 行：

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://stock_user:huojt@localhost:3306/stock_selection'
```

## 启动

```bash
pip install -r requirements.txt
python app.py
```

生产环境使用 gunicorn：

```bash
gunicorn -c gunicorn_conf.py app:app
```

## 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 主页面 |
| `GET /api/get_stocks?date=YYYY-MM-DD&rule=all` | 获取涨停股票及选股结果 |
| `GET /api/history_dates` | 获取有数据的日期列表 |
| `POST /api/clear_cache` | 清除指定日期缓存 |

## 数据库表

- `limit_up_stocks` - 涨停股票数据
- `selected_stocks` - 选股结果