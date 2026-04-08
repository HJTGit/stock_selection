from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import lunardate
import json
from typing import Dict, List, Optional
from sqlalchemy import func
import threading
import time
import apscheduler
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# MySQL数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://stock_user:huojt@localhost:3306/stock_selection'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)


# 数据模型
class LimitUpStock(db.Model):
    """涨停股票数据表"""
    __tablename__ = 'limit_up_stocks'

    id = db.Column(db.Integer, primary_key=True)
    trade_date = db.Column(db.Date, nullable=False, index=True)
    stock_code = db.Column(db.String(10), nullable=False, index=True)
    stock_name = db.Column(db.String(50), nullable=False)
    concept = db.Column(db.Text)
    close_price = db.Column(db.Float)
    change_percent = db.Column(db.Float)
    limit_up_price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('trade_date', 'stock_code', name='unique_stock_date'),
    )


class SelectedStock(db.Model):
    """选股结果表"""
    __tablename__ = 'selected_stocks'

    id = db.Column(db.Integer, primary_key=True)
    trade_date = db.Column(db.Date, nullable=False, index=True)
    stock_code = db.Column(db.String(10), nullable=False, index=True)
    stock_name = db.Column(db.String(50), nullable=False)
    concept = db.Column(db.Text)
    close_price = db.Column(db.Float)
    change_percent = db.Column(db.Float)
    limit_up_price = db.Column(db.Float)
    rule = db.Column(db.String(20))
    rule_code = db.Column(db.Integer)
    divisor = db.Column(db.Integer)
    calculation = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('trade_date', 'stock_code', 'rule_code', name='unique_selection'),
    )


# 创建数据库表
with app.app_context():
    db.create_all()


class StockSelectionSystem:
    def __init__(self):
        self.cache = {}

    def get_trading_date(self, date_str: str) -> Optional[str]:
        """获取实际交易日"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            # 如果是周末，调整为上一个周五
            if date_obj.weekday() >= 5:
                days_to_friday = (date_obj.weekday() - 4) % 7
                date_obj -= timedelta(days=days_to_friday)
            return date_obj.strftime('%Y%m%d')
        except:
            return None

    def get_next_trading_date(self, date_str: str) -> Optional[str]:
        """获取下一个交易日"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            for i in range(1, 8):
                next_date = date_obj + timedelta(days=i)
                if next_date.weekday() < 5:
                    return next_date.strftime('%Y%m%d')
            return None
        except:
            return None

    def save_limit_up_stocks_to_db(self, date_str: str, stocks: List[Dict]):
        """保存涨停股票数据到数据库"""
        try:
            trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            for stock in stocks:
                # 检查是否已存在
                existing = LimitUpStock.query.filter_by(
                    trade_date=trade_date,
                    stock_code=stock['code']
                ).first()

                if not existing:
                    limit_up_stock = LimitUpStock(
                        trade_date=trade_date,
                        stock_code=stock['code'],
                        stock_name=stock['name'],
                        concept=stock.get('concept', ''),
                        close_price=stock.get('close_price', 0),
                        change_percent=stock.get('change_percent', 0),
                        limit_up_price=stock.get('limit_up_price', 0)
                    )
                    db.session.add(limit_up_stock)

            db.session.commit()
            print(f"已保存{len(stocks)}只涨停股票数据到数据库，日期：{date_str}")

        except Exception as e:
            db.session.rollback()
            print(f"保存涨停股票数据失败: {e}")

    def get_limit_up_stocks_from_db(self, date_str: str) -> List[Dict]:
        """从数据库获取涨停股票数据"""
        try:
            trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            stocks = LimitUpStock.query.filter_by(trade_date=trade_date).all()

            result = []
            for stock in stocks:
                result.append({
                    'code': stock.stock_code,
                    'name': stock.stock_name,
                    'concept': stock.concept or '',
                    'close_price': stock.close_price,
                    'change_percent': stock.change_percent,
                    'limit_up_price': stock.limit_up_price
                })

            print(f"从数据库读取到{len(result)}只涨停股票，日期：{date_str}")
            return result

        except Exception as e:
            print(f"从数据库读取涨停股票失败: {e}")
            return []

    def save_selected_stocks_to_db(self, date_str: str, stocks: List[Dict]):
        """保存选股结果到数据库"""
        try:
            trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            for stock in stocks:
                # 检查是否已存在
                existing = SelectedStock.query.filter_by(
                    trade_date=trade_date,
                    stock_code=stock['code'],
                    rule_code=stock.get('rule_code', 0)
                ).first()

                if not existing:
                    selected_stock = SelectedStock(
                        trade_date=trade_date,
                        stock_code=stock['code'],
                        stock_name=stock['name'],
                        concept=stock.get('concept', ''),
                        close_price=stock.get('close_price', 0),
                        change_percent=stock.get('change_percent', 0),
                        limit_up_price=stock.get('limit_up_price', 0),
                        rule=stock.get('rule', ''),
                        rule_code=stock.get('rule_code', 0),
                        divisor=stock.get('divisor', 0),
                        calculation=stock.get('calculation', '')
                    )
                    db.session.add(selected_stock)

            db.session.commit()
            print(f"已保存{len(stocks)}条选股结果到数据库，日期：{date_str}")

        except Exception as e:
            db.session.rollback()
            print(f"保存选股结果失败: {e}")

    def get_selected_stocks_from_db(self, date_str: str, rule: str = 'all') -> List[Dict]:
        """从数据库获取选股结果"""
        try:
            trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            query = SelectedStock.query.filter_by(trade_date=trade_date)

            if rule == 'rule1':
                query = query.filter(SelectedStock.rule_code.in_([1]))
            elif rule == 'rule2':
                query = query.filter(SelectedStock.rule_code.in_([2]))
            elif rule == 'all':
                query = query.filter(SelectedStock.rule_code.in_([1, 2, 3]))

            stocks = query.all()

            result = []
            for stock in stocks:
                result.append({
                    'code': stock.stock_code,
                    'name': stock.stock_name,
                    'concept': stock.concept or '',
                    'close_price': stock.close_price,
                    'change_percent': stock.change_percent,
                    'limit_up_price': stock.limit_up_price,
                    'rule': stock.rule,
                    'rule_code': stock.rule_code,
                    'divisor': stock.divisor,
                    'calculation': stock.calculation
                })

            print(f"从数据库读取到{len(result)}条选股结果，日期：{date_str}，规则：{rule}")
            return result

        except Exception as e:
            print(f"从数据库读取选股结果失败: {e}")
            return []

    def get_limit_up_stocks(self, date_str: str, force_fresh: bool = False) -> List[Dict]:
        """获取涨停股票
        - 历史数据（不是今天）：优先从数据库读取
        - 当天数据：使用 akshare 接口实时获取
        """
        today = datetime.now().strftime('%Y-%m-%d')

        # 如果不是今天，优先从数据库获取历史数据
        if date_str != today:
            db_stocks = self.get_limit_up_stocks_from_db(date_str)
            if db_stocks:
                print(f"使用数据库历史数据，日期：{date_str}")
                return db_stocks
            # 历史数据数据库中没有，尝试从接口补采
            print(f"数据库中无 {date_str} 数据，尝试从接口补采")
            return self._fetch_stocks_from_api(date_str)

        # 今天是交易日，使用 akshare 接口
        return self._fetch_stocks_from_api(date_str)

    def _fetch_stocks_from_api(self, date_str: str) -> List[Dict]:
        """从 akshare 接口获取涨停股票数据"""
        trade_date = self.get_trading_date(date_str)
        if not trade_date:
            return []

        try:
            stocks = []

            try:
                # 方法1: 使用涨停股池
                df = ak.stock_zt_pool_em(date=trade_date)
                print(f"获取涨停股池数据成功，共{len(df)}条记录")

                for _, row in df.iterrows():
                    # 尝试获取概念信息
                    concept = ''
                    if '所属概念' in row:
                        concept = str(row['所属概念']) if not row['所属概念'].isna() else ''
                    elif '概念板块' in row:
                        concept = str(row['概念板块']) if not row['概念板块'].isna() else ''
                    elif '概念' in row:
                        concept = str(row['概念']) if not row['概念'].isna() else ''
                    else:
                        concept = str(row.get('所属行业', row.get('行业', '')))

                    stock = {
                        'code': str(row['代码']),
                        'name': row['名称'],
                        'concept': concept,
                        'close_price': row.get('最新价', row.get('收盘价', 0)),
                        'change_percent': row.get('涨跌幅', 0),
                        'limit_up_price': row.get('涨停价', 0)
                    }
                    stocks.append(stock)

            except Exception as e1:
                print(f"方法1失败: {e1}")

                try:
                    # 方法2: 使用涨停板数据
                    df = ak.stock_limit_up_daily(trade_date)
                    print(f"使用涨停板数据，共{len(df)}条记录")

                    for _, row in df.iterrows():
                        concept = str(row.get('所属概念', ''))
                        if not concept or concept == 'nan':
                            try:
                                stock_info = ak.stock_individual_info_em(symbol=row['代码'])
                                concept = str(stock_info.get('概念板块', stock_info.get('所属概念', '')))
                            except:
                                concept = ''

                        stock = {
                            'code': str(row['代码']),
                            'name': row['名称'],
                            'concept': concept,
                            'close_price': row.get('最新价', row.get('收盘价', 0)),
                            'change_percent': row.get('涨跌幅', 0),
                            'limit_up_price': row.get('涨停价', 0)
                        }
                        stocks.append(stock)

                except Exception as e2:
                    print(f"方法2失败: {e2}")
                    stocks = self.get_mock_stocks(date_str)

            # 保存到数据库
            if stocks:
                self.save_limit_up_stocks_to_db(date_str, stocks)

            return stocks

        except Exception as e:
            print(f"获取涨停股票失败: {e}")
            stocks = self.get_mock_stocks(date_str)
            if stocks:
                self.save_limit_up_stocks_to_db(date_str, stocks)
            return stocks

    def get_mock_stocks(self, date_str: str) -> List[Dict]:
        """模拟涨停股票数据（带完整概念信息）"""
        # ...（保持原有的模拟数据不变）
        mock_stocks = [
            # ...（原有的模拟数据）
        ]

        return mock_stocks

    def get_lunar_date(self, date_str: str) -> Dict:
        """获取农历日期"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            lunar = lunardate.LunarDate.fromSolarDate(
                date_obj.year, date_obj.month, date_obj.day
            )
            return {
                'year': lunar.year,
                'month': lunar.month,
                'day': lunar.day
            }
        except:
            return {'month': 1, 'day': 1}

    def selection_rule_1(self, stocks: List[Dict], date_str: str) -> List[Dict]:
        """规则1：代码除以下一交易日的月份+日"""
        next_date = self.get_next_trading_date(date_str)
        if not next_date:
            return []

        try:
            next_month = int(next_date[4:6])
            next_day = int(next_date[6:8])
            divisor = next_month + next_day

            if divisor == 0:
                return []

            selected = []
            for stock in stocks:
                try:
                    # 处理不同格式的股票代码
                    code = stock['code']
                    if code.startswith('sh') or code.startswith('sz'):
                        code_num = int(code[2:8])
                    else:
                        code_num = int(code[:6])

                    if code_num % divisor == 0:
                        stock_copy = stock.copy()
                        stock_copy['rule'] = '规则1'
                        stock_copy['rule_code'] = 1
                        stock_copy['divisor'] = divisor
                        stock_copy['calculation'] = f'{code_num} % {divisor} = 0'
                        selected.append(stock_copy)
                except:
                    continue
            return selected
        except:
            return []

    def selection_rule_2(self, stocks: List[Dict], date_str: str) -> List[Dict]:
        """规则2：代码除以农历月份+日"""
        lunar_date = self.get_lunar_date(date_str)
        divisor = lunar_date['month'] + lunar_date['day']

        if divisor == 0:
            return []

        selected = []
        for stock in stocks:
            try:
                # 处理不同格式的股票代码
                code = stock['code']
                if code.startswith('sh') or code.startswith('sz'):
                    code_num = int(code[2:8])
                else:
                    code_num = int(code[:6])

                if code_num % divisor == 0:
                    stock_copy = stock.copy()
                    stock_copy['rule'] = '规则2'
                    stock_copy['rule_code'] = 2
                    stock_copy['divisor'] = divisor
                    stock_copy['calculation'] = f'{code_num} % {divisor} = 0'
                    selected.append(stock_copy)
            except:
                continue
        return selected

    def enhance_concept_info(self, stocks: List[Dict]) -> List[Dict]:
        """增强概念信息"""
        concept_map = {
            '000001': '银行,互联网金融,金融科技,数字人民币',
            '000858': '白酒,消费,食品饮料,国企改革',
            '002415': '安防,人工智能,机器视觉,物联网,智慧城市',
            '300750': '新能源车,锂电池,储能,动力电池,固态电池',
            '600519': '白酒,消费,食品饮料,高端制造,国企改革',
            '002594': '新能源车,锂电池,汽车整车,华为汽车,固态电池',
            '300059': '互联网金融,证券,金融科技,人工智能',
            '603259': '生物医药,CRO,创新药,医疗健康',
            '000002': '房地产,物业管理,租赁同权',
            '002049': '芯片,半导体,国产替代,物联网',
            '600276': '生物医药,创新药,医疗健康',
            '601318': '保险,金融科技,人工智能,互联网保险',
        }

        for stock in stocks:
            code_short = stock['code'][:6]  # 取6位数字代码
            if code_short in concept_map and (not stock.get('concept') or len(stock['concept']) < 3):
                stock['concept'] = concept_map[code_short]

        return stocks


# 创建系统实例
stock_system = StockSelectionSystem()


def save_today_data_after_close():
    """收盘后自动保存当日数据到数据库（定时任务）"""
    today = datetime.now().strftime('%Y-%m-%d')
    weekday = datetime.now().weekday()

    # 仅在交易日（周一到周五）执行
    if weekday >= 5:
        print(f"今日是周末，跳过自动保存")
        return

    print(f"执行收盘后自动保存任务，日期：{today}")
    try:
        # 获取今日涨停股票数据
        stocks = stock_system._fetch_stocks_from_api(today)
        if stocks:
            print(f"收盘后自动保存成功，共 {len(stocks)} 只涨停股票")
        else:
            print(f"收盘后自动保存完成，但未获取到数据")
    except Exception as e:
        print(f"收盘后自动保存失败: {e}")


# 配置定时任务调度器：每个交易日 15:35 执行
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=save_today_data_after_close,
    trigger='cron',
    hour=15,
    minute=35,
    day_of_week='mon-fri',
    id='save_after_close',
    replace_existing=True
)
scheduler.start()
print("定时任务已启动：每个交易日 15:35 自动保存当日涨停数据")


@app.route('/')
def index():
    """主页面"""
    # 设置默认日期为今天
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', today=today)


@app.route('/api/get_stocks', methods=['GET'])
def get_stocks():
    """获取涨停股票和选股结果"""
    date_str = request.args.get('date')
    rule = request.args.get('rule', 'all')
    force_fresh = request.args.get('force_fresh', 'True').lower() == 'true'

    if not date_str:
        return jsonify({'error': '请选择日期'}), 400

    try:
        # 先尝试从数据库获取选股结果
        if not force_fresh:
            selected_stocks = stock_system.get_selected_stocks_from_db(date_str, rule)
            if selected_stocks:
                # 获取涨停股票数量（用于显示）
                limit_up_stocks = stock_system.get_limit_up_stocks_from_db(date_str)
                limit_up_count = len(limit_up_stocks) if limit_up_stocks else 0

                # 获取农历日期
                lunar_date = stock_system.get_lunar_date(date_str)

                response = {
                    'date': date_str,
                    'lunar_date': f'{lunar_date["month"]}月{lunar_date["day"]}日',
                    'limit_up_stocks': limit_up_stocks,
                    'selected_stocks': selected_stocks,
                    'limit_up_count': limit_up_count,
                    'selected_count': len(selected_stocks),
                    'from_db': True
                }
                return jsonify(response)

        # 数据库没有选股结果或强制刷新，重新计算
        # 获取涨停股票
        limit_up_stocks = stock_system.get_limit_up_stocks(date_str, force_fresh)

        # 增强概念信息
        limit_up_stocks = stock_system.enhance_concept_info(limit_up_stocks)

        # 根据规则选股
        selected_stocks = []
        if rule == 'rule1' or rule == 'all':
            selected_stocks.extend(stock_system.selection_rule_1(limit_up_stocks, date_str))

        if rule == 'rule2' or rule == 'all':
            selected_stocks.extend(stock_system.selection_rule_2(limit_up_stocks, date_str))

        # 去除重复的股票（可能同时符合两个规则）
        unique_selected = {}
        for stock in selected_stocks:
            code = stock['code']
            if code not in unique_selected:
                unique_selected[code] = stock
            else:
                # 如果已存在，合并规则信息
                existing = unique_selected[code]
                existing['rule'] = '多策略'
                existing['rule_code'] = 3  # 3表示多策略

        selected_stocks = list(unique_selected.values())

        # 保存选股结果到数据库
        if selected_stocks:
            stock_system.save_selected_stocks_to_db(date_str, selected_stocks)

        # 获取农历日期
        lunar_date = stock_system.get_lunar_date(date_str)

        response = {
            'date': date_str,
            'lunar_date': f'{lunar_date["month"]}月{lunar_date["day"]}日',
            'limit_up_stocks': limit_up_stocks,
            'selected_stocks': selected_stocks,
            'limit_up_count': len(limit_up_stocks),
            'selected_count': len(selected_stocks),
            'from_db': False
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': f'获取数据失败: {str(e)}'}), 500


@app.route('/api/get_stock_concept', methods=['GET'])
def get_stock_concept():
    """单独获取股票概念信息"""
    stock_code = request.args.get('code')

    if not stock_code:
        return jsonify({'error': '请输入股票代码'}), 400

    try:
        # 尝试获取股票概念信息
        import akshare as ak
        stock_info = ak.stock_individual_info_em(symbol=stock_code)

        concept = ''
        if '概念板块' in stock_info:
            concept = stock_info['概念板块']
        elif '所属概念' in stock_info:
            concept = stock_info['所属概念']
        elif '概念' in stock_info:
            concept = stock_info['概念']

        return jsonify({
            'code': stock_code,
            'concept': concept
        })

    except Exception as e:
        # 如果失败，返回模拟概念
        concept_map = {
            '000001': '银行,互联网金融,金融科技,数字人民币',
            '000858': '白酒,消费,食品饮料,国企改革',
            '002415': '安防,人工智能,机器视觉,物联网,智慧城市',
            '300750': '新能源车,锂电池,储能,动力电池,固态电池',
            '600519': '白酒,消费,食品饮料,高端制造,国企改革',
        }

        code_short = stock_code[:6]
        concept = concept_map.get(code_short, '暂无概念信息')

        return jsonify({
            'code': stock_code,
            'concept': concept
        })


@app.route('/api/history_dates', methods=['GET'])
def get_history_dates():
    """获取有历史数据的日期列表"""
    try:
        # 从涨停股票表获取有数据的日期
        dates = db.session.query(
            func.date_format(LimitUpStock.trade_date, '%Y-%m-%d')
        ).distinct().order_by(LimitUpStock.trade_date.desc()).all()

        date_list = [date[0] for date in dates]

        return jsonify({
            'dates': date_list,
            'count': len(date_list)
        })

    except Exception as e:
        return jsonify({'error': f'获取历史日期失败: {str(e)}'}), 500


@app.route('/api/clear_cache', methods=['POST'])
def clear_cache():
    """清除指定日期的缓存"""
    try:
        date_str = request.json.get('date')

        if not date_str:
            return jsonify({'error': '请指定日期'}), 400

        trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # 删除涨停股票数据
        LimitUpStock.query.filter_by(trade_date=trade_date).delete()

        # 删除选股结果
        SelectedStock.query.filter_by(trade_date=trade_date).delete()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'已清除{date_str}的缓存数据'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'清除缓存失败: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)