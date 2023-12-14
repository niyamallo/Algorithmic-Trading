import bybit
import pandas as pd
from datetime import datetime
import win32api
import time
import pprint
import talib


def get_api():
    api_key = "blank"
    api_secret = "blank"
    return api_key, api_secret


def get_account():
    my_api_key, my_api_secret = get_api()
    client = bybit.bybit(test=False, api_key=my_api_key, api_secret=my_api_secret)
    return client


def change_leverage_process():
    while True:
        answer = input("BTC/USDT 레버리지를 변경하시겠습니까?[y/n]")
        if answer.lower() == 'y':
            client = get_account()
            print("BTC/USDT 레버리지를 변경합니다.")
            my_buy_leverage = float(input("공매수 레버리지 입력 :"))
            my_sell_leverage = float(input("공매도 레버리지 입력 :"))
            rep = client.LinearPositions.LinearPositions_saveLeverage(symbol="BTCUSDT", buy_leverage=my_buy_leverage,
                                                                      sell_leverage=my_sell_leverage).result()[0]
            if rep['ret_code'] == 0 and rep['ext_code'] == "":
                print("레버리지 입력 완료")
                break
            else:
                print("레버리지 변경이 불가능합니다.")
                pprint.pprint(rep)
        elif answer.lower() == 'n':
            print("레버리지 변경안함.")
            break
        else:
            print('잘못 입력하였습니다. 다시 입력해주세요')


def get_chart_data(my_interval=3):
    is_time_correct = False
    while not (is_time_correct):
        client = get_account()
        start_time = float(client.Common.Common_getTime().result()[0]['time_now']) - (
                    1 * 60 * my_interval * 300)  # 60초x인터벌x300봉
        dict_ = {'from': start_time}
        result = client.Kline.Kline_get(symbol="BTCUSD", interval=str(my_interval), **dict_).result()
        data = result[0]['result']
        df = pd.DataFrame(data, columns=['open_time', 'open', 'high', 'low', 'close', 'volume'])

        start_time2 = float(client.Common.Common_getTime().result()[0]['time_now']) - (
                    1 * 60 * my_interval * 150)  # 60초x인터벌x150봉
        dict_2 = {'from': start_time2}
        result2 = client.Kline.Kline_get(symbol="BTCUSD", interval=str(my_interval), **dict_2).result()
        data2 = result2[0]['result']
        df2 = pd.DataFrame(data2, columns=['open_time', 'open', 'high', 'low', 'close', 'volume'])
        df = df.append(df2)
        df = df.drop_duplicates()

        df['open'] = pd.to_numeric(df['open'])
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['volume'] = pd.to_numeric(df['volume'])

        df['open_time'] = pd.to_datetime(df['open_time'] + 32400, unit='s')  # 미국 한국 시간차 9시간 = 32400초
        current_time = datetime.fromtimestamp(
            datetime.now().timestamp() - datetime.now().timestamp() % (60 * my_interval))
        is_time_correct = (df['open_time'].iloc[-1] == current_time)

    return df


def SMA(chart_data, period=240, column='close'):
    return chart_data[column].rolling(window=period).mean()


# 차트를 입력받아 '음뚫', '양뚫', '양뚫양', '양뚫음', '음뚫양', '음뚫음', '대기' 중 하나의 문자열을 반환한다.
def get_namutrading_state(chart_data):
    ma240 = SMA(chart_data, 240)
    ma250 = SMA(chart_data, 250)
    ma260 = SMA(chart_data, 260)
    ma270 = SMA(chart_data, 270)
    ma280 = SMA(chart_data, 280)

    min_value = min(ma240.iloc[-2], ma250.iloc[-2], ma260.iloc[-2], ma270.iloc[-2], ma280.iloc[-2])
    max_value = max(ma240.iloc[-2], ma250.iloc[-2], ma260.iloc[-2], ma270.iloc[-2], ma280.iloc[-2])

    if chart_data['open'].iloc[-2] < min_value and chart_data['close'].iloc[-2] > max_value:
        # 양봉으로 뚫음
        return '양뚫'

    elif chart_data['open'].iloc[-2] > max_value and chart_data['close'].iloc[-2] < min_value:
        # 음봉으로 뚫음
        return '음뚫'
    else:
        # 양뚫, 음뚫이 아닐때 즉, 현재상황이 양뚫, 음뚫이 아니기때문에 양뚫, 음뚫인 경우의 수는 생각안해도 됨
        min_value2 = min(ma240.iloc[-3], ma250.iloc[-3], ma260.iloc[-3], ma270.iloc[-3], ma280.iloc[-3])
        max_value2 = max(ma240.iloc[-3], ma250.iloc[-3], ma260.iloc[-3], ma270.iloc[-3], ma280.iloc[-3])

        if chart_data['open'].iloc[-3] < min_value2 and chart_data['close'].iloc[-3] > max_value2 and \
                chart_data['open'].iloc[-2] < chart_data['close'].iloc[-2]:
            # 양봉으로 뚫고, 그다음 양봉이라면
            return "양뚫양"

        elif chart_data['open'].iloc[-3] < min_value2 and chart_data['close'].iloc[-3] > max_value2 and \
                chart_data['open'].iloc[-2] > chart_data['close'].iloc[-2]:
            # 양봉으로 뚫고, 그다음 음봉이라면
            return "양뚫음"

        elif chart_data['open'].iloc[-3] > max_value2 and chart_data['close'].iloc[-3] < min_value2 and \
                chart_data['open'].iloc[-2] < chart_data['close'].iloc[-2]:
            # 음봉으로 뚫고, 그다음 양봉이라면
            return "음뚫양"

        elif chart_data['open'].iloc[-3] > max_value2 and chart_data['close'].iloc[-3] < min_value2 and \
                chart_data['open'].iloc[-2] > chart_data['close'].iloc[-2]:
            # 음봉으로 뚫고, 또 음봉=>매도 포지션
            return "음뚫음"

        else:
            return "대기"  # 일반신호 리턴


def is_float(string_):
    try:
        float(string_)
        return True
    except ValueError:
        return False


def set_quantity():
    while True:
        print("거래 가능한 수량만 입력하세요. 입력에 주의해주세요.")
        buy_qty = input("공매수 수량 입력:")
        sell_qty = input("공매도 수량 입력:")
        if is_float(buy_qty) and is_float(sell_qty):
            buy_qty = float(buy_qty)
            sell_qty = float(sell_qty)
            break
        else:
            print("숫자만 입력하세요")
    return buy_qty, sell_qty

def delete_order(client):
    rep = client.LinearOrder.LinearOrder_cancelAll(symbol="BTCUSDT").result()[0]
    if rep['ret_code'] == 0 and rep['ext_code'] == "":
        print("사용자가 걸어놓은 주문 삭제")
    else:
        print("사용자가 걸어놓은 주문 삭제 실패")
        pprint.pprint(rep)
    return rep


#공매도 청산 함수, sell_qty는 수량
def sell_close(client, sell_qty):
    rep = client.LinearOrder.LinearOrder_new(side="Buy", symbol="BTCUSDT", order_type="Market", qty=sell_qty, \
                                           time_in_force="GoodTillCancel", reduce_only=True,
                                           close_on_trigger=False).result()[0]
    if rep['ret_code'] == 0 and rep['ext_code'] == "":
        print("공매도 청산 성공")
    else:
        print("공매도 청산 실패 / 잔액, 수량 확인바람")
        pprint.pprint(rep)
    return rep

#공매수 진입 함수, buy_qty는 수량
def buy_open(client, buy_qty):
    rep = client.LinearOrder.LinearOrder_new(side="Buy", symbol="BTCUSDT", order_type="Market", qty=buy_qty, \
                                           time_in_force="GoodTillCancel", reduce_only=False,
                                           close_on_trigger=False).result()[0]
    if rep['ret_code'] == 0 and rep['ext_code'] == "":
        print("공매수 진입 성공")
    else:
        print("공매수 진입 실패 / 잔액, 수량 확인바람")
        pprint.pprint(rep)
    return rep

#공매수 청산
def buy_close(client, buy_qty):
    rep = client.LinearOrder.LinearOrder_new(side="Sell", symbol="BTCUSDT", order_type="Market", qty=buy_qty, \
                                           time_in_force="GoodTillCancel", reduce_only=True,
                                           close_on_trigger=False).result()[0]
    if rep['ret_code'] == 0 and rep['ext_code'] == "":
        print("공매수 청산 성공")
    else:
        print("공매수 청산 실패 / 잔액, 수량 확인바람")
        pprint.pprint(rep)
    return rep

#공매도 진입
def sell_open(client, sell_qty):
    rep = client.LinearOrder.LinearOrder_new(side="Sell", symbol="BTCUSDT", order_type="Market", qty=sell_qty, \
                                           time_in_force="GoodTillCancel", reduce_only=False,
                                           close_on_trigger=False).result()[0]
    if rep['ret_code'] == 0 and rep['ext_code'] == "":
        print("공매도 진입 성공")
    else:
        print("공매도 진입 실패 / 잔액, 수량 확인바람")
        pprint.pprint(rep)
    return rep

# str_은 알람내용
def alarm(str_):
    for i in range(5):
        win32api.Beep(537, 2500)
        print(str_)

# 포지션 확인 함수, 단, 포지션은 항상 하나만 가질수 있다고 가정함. 즉, 양방향 포지션 불가능.
def check_my_position_and_size(client):
    rep = client.LinearPositions.LinearPositions_myPosition(symbol="BTCUSDT").result()[0]
    position = 'None'
    size = 0
    for result in rep['result']:
        if float(result['size']) != 0:
            position = result['side']
            size = float(result['size'])
            break
    return position, size

def get_my_entry_price(client):
    rep = client.LinearPositions.LinearPositions_myPosition(symbol="BTCUSDT").result()[0]
    entry_price = 0
    for result in rep['result']:
        if float(result['entry_price']) != 0:
            entry_price = float(rep['result'][0]['entry_price'])
            break
    return entry_price

def get_last_candle_price(client, interval):
    start_time = float(client.Common.Common_getTime().result()[0]['time_now']) - (
            1 * 60 * interval * 2)  # 60초x인터벌x300봉
    dict_ = {'from': start_time}
    current_price = client.LinearKline.LinearKline_get(symbol="BTCUSDT", interval=str(interval),
                                                       **dict_).result()[0]['result'][0]['close']
    return current_price

def run_process(buy_qty, sell_qty, interval=3):
    error_ = True
    while True:
        now = datetime.now()
        if now.minute % interval != 0 or now.second > 5:
            log = f"{now.hour}시 {now.minute}분 {now.second}초"
            print(log)
            error_ = True
            time.sleep(1)
        else:
            # 동작중에 알수 없는 에러가 나오면 안날때까지 반복하기 위해 error_변수에 True를 미리 할당
            # error_가 참일경우 계속 반복
            while error_:
                chart_data = get_chart_data(interval)
                result = get_namutrading_state(chart_data)
                client = get_account()
                position, size = check_my_position_and_size(client)
                
                if result in ['양뚫양', '음뚫양']:
                    # 이전과 같은 포지션일땐 사용자 주문을 유지하지만, 포지션이 바뀌거나 없을때, 사용자 주문을 일괄 취소함.
                    if position != 'Buy':           #현재 포지션이 없거나 숏이라면 사용자 주문 전체 취소, 그 중 숏일땐 전부청산
                        ##사용자 주문삭제##
                        delete_order(client)
                        if position == 'Sell':
                            ##공매도 전부 청산##
                            sell_close(client, size)
                    ##공매수 진입##
                    rep = buy_open(client, buy_qty)

                    # 알림
                    alarm("롱 시그널 입니다.")

                elif result in ['양뚫음', '음뚫음']:
                    # 이전과 같은 포지션일땐 사용자 주문을 유지하지만, 포지션이 바뀌거나 없을때, 사용자 주문을 일괄 취소함.
                    if position != 'Sell':  # 현재 포지션이 없거나 롱이라면 사용자 주문 전체 취소, 그 중 롱일땐 전부청산
                        ##사용자 주문삭제##
                        delete_order(client)
                        if position == 'Buy':
                            ##공매수 전부 청산##
                            buy_close(client, size)
                    ##공매도 진입##
                    rep = sell_open(client, sell_qty)
                    
                    # 알림
                    alarm("숏 시그널 입니다.")

                elif result == '양뚫':
                    alarm("↑↑양뚫↑↑입니다. 대기하세요.")

                elif result == '음뚫':
                    alarm("↓↓음뚫↓↓입니다. 대기하세요")

                else:
                    print("아무런 시그널이 없습니다.")

                error_ = False    
                now = datetime.now()
            print(f"{now.hour}시 {now.minute}분 {now.second}초")
            time.sleep(1)

if __name__ == '__main__':
    change_leverage_process()
    buy_qty, sell_qty = set_quantity()
    while True:
        try:
            run_process(buy_qty, sell_qty)
        except Exception as e:
            print(e)
        finally:
            pass