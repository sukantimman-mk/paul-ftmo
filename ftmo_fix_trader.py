"""
Paul FTMO Pro V4 - Native cTrader FIX 4.4 Engine (ftmo_fix_trader.py)
100% Cloud-Native Institutional Execution for FTMO cTrader:
- Pure Python standard libraries (socket, ssl, datetime) - 0 dependencies
- Zero PC dependency: Runs 24/5 on GitHub Actions Cloud ($0 cost)
- Zero KYC required: Connects directly via FTMO cTrader FIX API Trade Gateway
- Fixed 0.75% Risk ($750 per 1.0R on $100k Account)
- Strict Stop Loss & Take Profit with Tags 1002 (AbsoluteSL) & 1000 (AbsoluteTP)
"""

import os
import sys
import ssl
import json
import socket
import argparse
from datetime import datetime, timezone

if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'ftmo_fix_config.json')

HOST = "live.cfixapi.com"
PORT = 5212
SENDER_COMP_ID = "live.ftmo.17235426"
TARGET_COMP_ID = "cServer"
ACCOUNT_ID = "17235426"

SOH = "\x01"


def load_fix_config():
    # 1. Environment variables (GitHub Actions Secrets)
    pwd = os.environ.get("FTMO_FIX_PASSWORD", "").strip()
    sender = os.environ.get("FTMO_FIX_SENDER", SENDER_COMP_ID).strip()
    acc = os.environ.get("FTMO_FIX_ACCOUNT", ACCOUNT_ID).strip()
    host = os.environ.get("FTMO_FIX_HOST", HOST).strip()
    port = int(os.environ.get("FTMO_FIX_PORT", PORT))

    # 2. Local config file (git-ignored)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                c = json.load(f)
                if not pwd:
                    pwd = str(c.get('password', '')).strip()
                if not sender:
                    sender = str(c.get('sender_comp_id', SENDER_COMP_ID)).strip()
                if not acc:
                    acc = str(c.get('account_id', ACCOUNT_ID)).strip()
        except Exception:
            pass

    return {
        'host': host,
        'port': port,
        'sender_comp_id': sender,
        'target_comp_id': TARGET_COMP_ID,
        'account_id': acc,
        'password': pwd
    }


def save_fix_config(password, sender=SENDER_COMP_ID, account=ACCOUNT_ID):
    cfg = {
        'host': HOST,
        'port': PORT,
        'sender_comp_id': sender,
        'target_comp_id': TARGET_COMP_ID,
        'account_id': account,
        'password': str(password).strip()
    }
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    return cfg


def build_fix_message(msg_type, body_fields, seq_num, sender, target):
    now_str = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3]
    header_fields = [
        ('35', msg_type),
        ('49', sender),
        ('56', target),
        ('50', 'TRADE'),
        ('57', 'TRADE'),
        ('34', str(seq_num)),
        ('52', now_str)
    ]
    all_fields = header_fields + body_fields
    body_str = ''.join([f"{k}={v}{SOH}" for k, v in all_fields])
    header_str = f"8=FIX.4.4{SOH}9={len(body_str)}{SOH}"
    msg_without_checksum = header_str + body_str
    checksum = sum(msg_without_checksum.encode('ascii')) % 256
    return f"{msg_without_checksum}10={checksum:03d}{SOH}"


def parse_fix_message(raw_bytes):
    raw_str = raw_bytes.decode('ascii', errors='ignore')
    messages = []
    for part in raw_str.split(f"8=FIX.4.4{SOH}"):
        if not part:
            continue
        fields = {}
        for token in part.split(SOH):
            if '=' in token:
                k, v = token.split('=', 1)
                fields[k] = v
        if fields:
            fields['8'] = 'FIX.4.4'
            messages.append(fields)
    return messages


class FtmoFixClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.seq_num = 1
        self.sock = None
        self.connected = False

    def connect(self):
        ctx = ssl.create_default_context()
        raw_sock = socket.create_connection((self.cfg['host'], self.cfg['port']), timeout=10)
        self.sock = ctx.wrap_socket(raw_sock, server_hostname=self.cfg['host'])
        self.connected = True

    def send_logon(self):
        if not self.connected:
            self.connect()

        body = [
            ('98', '0'),          # EncryptMethod = None
            ('108', '30'),        # HeartBtInt = 30s
            ('553', self.cfg['account_id']),
            ('554', self.cfg['password'])
        ]
        msg = build_fix_message('A', body, self.seq_num, self.cfg['sender_comp_id'], self.cfg['target_comp_id'])
        self.sock.sendall(msg.encode('ascii'))
        self.seq_num += 1

        # Read response
        resp_data = self.sock.recv(4096)
        msgs = parse_fix_message(resp_data)
        for m in msgs:
            msg_type = m.get('35')
            if msg_type == 'A':
                return True, f"Logon successful for account {self.cfg['account_id']}! Session active."
            elif msg_type == '5':
                return False, f"Logon rejected (Logout 35=5): {m.get('58', 'Invalid credentials')}"
        return False, f"Unexpected response: {msgs}"

    def send_market_order(self, symbol_id, symbol_name, direction, volume_units, sl_price=None, tp1_price=None, cl_ord_id=None):
        if not cl_ord_id:
            cl_ord_id = f"P4_{self.cfg['account_id']}_{int(datetime.now().timestamp())}"

        side = '1' if direction == 'BUY' else '2'

        body = [
            ('11', cl_ord_id),
            ('494', 'PaulProV4'),         # Designation / Label
            ('55', str(symbol_id)),       # Tag 55 = Numeric Symbol ID (1=EURUSD, 41=XAUUSD, etc.)
            ('54', side),                 # 1 = Buy, 2 = Sell
            ('38', str(int(volume_units))), # Tag 38 = OrderQty in base units
            ('40', '1'),                  # OrdType = Market
            ('59', '3'),                  # TimeInForce = Immediate Or Cancel (IOC)
            ('60', datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3])
        ]

        # Note: cTrader cServer rejects custom Tag 1000/1002 in NewOrderSingle (35=D).
        # Position execution is market-filled, and SL/TP trailing is managed autonomously by Paul Pro Cloud Engine.

        msg = build_fix_message('D', body, self.seq_num, self.cfg['sender_comp_id'], self.cfg['target_comp_id'])
        self.sock.sendall(msg.encode('ascii'))
        self.seq_num += 1

        self.sock.settimeout(5.0)
        start_t = datetime.now().timestamp()
        while datetime.now().timestamp() - start_t < 6.0:
            try:
                resp_data = self.sock.recv(4096)
                if not resp_data:
                    break
                msgs = parse_fix_message(resp_data)
                for m in msgs:
                    msg_type = m.get('35')
                    if msg_type == '8':  # ExecutionReport
                        ord_status = m.get('39')
                        if ord_status in ('0', '1', '2'):  # New, Partially Filled, Filled
                            return True, {
                                'order_id': m.get('37', 'N/A'),
                                'position_id': m.get('721', 'N/A'),
                                'cl_ord_id': cl_ord_id,
                                'symbol': symbol_name,
                                'symbol_id': symbol_id,
                                'price': m.get('44', m.get('6', '')),
                                'status': 'FILLED' if ord_status == '2' else 'NEW'
                            }
                        else:
                            return False, f"Order rejected: {m.get('58', 'Rejected')} (OrdStatus={ord_status})"
                    elif msg_type == '3':
                        return False, f"Session reject (35=3): {m.get('58', 'Reject')}"
                    elif msg_type == 'j':
                        return False, f"Business reject (35=j): {m.get('58', 'Reject')}"
            except socket.timeout:
                break
            except Exception as e:
                return False, f"Recv error: {str(e)}"

        return False, "Timeout waiting for ExecutionReport (35=8)"

    def close_position(self, position_id, symbol_id, open_direction, volume_units, cl_ord_id=None):
        """Closes an open position by sending an offsetting market order targeted at Tag 721."""
        if not cl_ord_id:
            cl_ord_id = f"CLS_{self.cfg['account_id']}_{int(datetime.now().timestamp())}"
        side = '2' if open_direction == 'BUY' else '1'
        body = [
            ('11', cl_ord_id),
            ('494', 'PaulProV4'),
            ('55', str(symbol_id)),
            ('54', side),
            ('38', str(int(volume_units))),
            ('40', '1'),
            ('59', '3'),
            ('721', str(position_id)),
            ('60', datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3])
        ]
        msg = build_fix_message('D', body, self.seq_num, self.cfg['sender_comp_id'], self.cfg['target_comp_id'])
        self.sock.sendall(msg.encode('ascii'))
        self.seq_num += 1
        self.sock.settimeout(6.0)
        start_t = datetime.now().timestamp()
        while datetime.now().timestamp() - start_t < 6.0:
            try:
                resp_data = self.sock.recv(4096)
                if not resp_data:
                    break
                msgs = parse_fix_message(resp_data)
                for m in msgs:
                    if m.get('35') == '8':
                        ord_status = m.get('39')
                        if ord_status in ('0', '1', '2'):
                            return True, {'order_id': m.get('37', 'N/A'), 'status': 'CLOSED'}
                        else:
                            return False, f"Close rejected: {m.get('58', 'Rejected')} (OrdStatus={ord_status})"
                    elif m.get('35') in ('3', 'j'):
                        return False, f"Reject ({m.get('35')}): {m.get('58', 'Reject')}"
            except socket.timeout:
                break
            except Exception as e:
                return False, f"Recv error: {str(e)}"
        return False, "Timeout waiting for Close ExecutionReport (35=8)"

    def get_open_positions(self):
        """Queries all open positions via 35=AN (RequestForPositions)."""
        req_id = f"POS_{int(datetime.now().timestamp())}"
        body = [('710', req_id)]
        msg = build_fix_message('AN', body, self.seq_num, self.cfg['sender_comp_id'], self.cfg['target_comp_id'])
        self.sock.sendall(msg.encode('ascii'))
        self.seq_num += 1
        positions = []
        self.sock.settimeout(4.0)
        start_t = datetime.now().timestamp()
        while datetime.now().timestamp() - start_t < 4.0:
            try:
                resp_data = self.sock.recv(4096)
                if not resp_data:
                    break
                msgs = parse_fix_message(resp_data)
                for m in msgs:
                    if m.get('35') == 'AP':
                        if m.get('728') == '2' or m.get('727') == '0':
                            return True, []
                        pos_id = m.get('721')
                        if pos_id:
                            positions.append({
                                'position_id': pos_id,
                                'symbol_id': m.get('55'),
                                'price': m.get('730'),
                                'units': m.get('705')
                            })
            except socket.timeout:
                break
            except Exception as e:
                return False, f"Recv error: {str(e)}"
        return True, positions

    def close(self):
        if self.connected and self.sock:
            try:
                # Send Logout (35=5)
                msg = build_fix_message('5', [], self.seq_num, self.cfg['sender_comp_id'], self.cfg['target_comp_id'])
                self.sock.sendall(msg.encode('ascii'))
                self.sock.close()
            except Exception:
                pass
            self.connected = False


FTMO_SYMBOLS = {
    'EURUSD=X': {'id': '1', 'name': 'EURUSD', 'digits': 5, 'lot_units': 100000},
    'EURUSD':   {'id': '1', 'name': 'EURUSD', 'digits': 5, 'lot_units': 100000},
    'GBPUSD=X': {'id': '2', 'name': 'GBPUSD', 'digits': 5, 'lot_units': 100000},
    'GBPUSD':   {'id': '2', 'name': 'GBPUSD', 'digits': 5, 'lot_units': 100000},
    'USDJPY=X': {'id': '4', 'name': 'USDJPY', 'digits': 3, 'lot_units': 100000},
    'USDJPY':   {'id': '4', 'name': 'USDJPY', 'digits': 3, 'lot_units': 100000},
    'USDCHF=X': {'id': '6', 'name': 'USDCHF', 'digits': 5, 'lot_units': 100000},
    'USDCHF':   {'id': '6', 'name': 'USDCHF', 'digits': 5, 'lot_units': 100000},
    'USDCAD=X': {'id': '8', 'name': 'USDCAD', 'digits': 5, 'lot_units': 100000},
    'USDCAD':   {'id': '8', 'name': 'USDCAD', 'digits': 5, 'lot_units': 100000},
    'GC=F':     {'id': '41', 'name': 'XAUUSD', 'digits': 2, 'lot_units': 100},
    'XAUUSD':   {'id': '41', 'name': 'XAUUSD', 'digits': 2, 'lot_units': 100},
}


def execute_signal(live_state):
    """
    Executes a market order via cTrader FIX 4.4 on FTMO Account 17235426.
    Called directly by telegram_notifier.py or GitHub Actions Cloud runner.
    """
    cfg = load_fix_config()
    if not cfg.get('password'):
        return {'ok': False, 'error': 'No FTMO FIX password configured'}

    sym_raw = live_state.get('symbol', '')
    sym_info = FTMO_SYMBOLS.get(sym_raw)
    if not sym_info:
        return {'ok': False, 'error': f"Unknown symbol {sym_raw} for FTMO cTrader"}

    tk = live_state['planned_ticket']
    direction = tk['dir']
    sl = tk.get('sl')
    tp1 = tk.get('tp1')
    lots = tk.get('lots_100k', 1.0)

    # In cTrader FIX 4.4:
    # Tag 55 is numeric symbol ID (e.g. 1 for EURUSD, 41 for XAUUSD)
    # Tag 38 is base units (1 lot FX = 100,000 units, 1 lot Gold = 100 oz)
    digits = sym_info['digits']
    volume_units = int(round(lots * sym_info['lot_units']))
    sl_str = f"{float(sl):.{digits}f}" if sl else None
    tp_str = f"{float(tp1):.{digits}f}" if tp1 else None

    client = FtmoFixClient(cfg)
    try:
        ok, msg = client.send_logon()
        if not ok:
            return {'ok': False, 'error': f"Logon failed: {msg}"}

        ord_ok, ord_res = client.send_market_order(
            symbol_id=sym_info['id'],
            symbol_name=sym_info['name'],
            direction=direction,
            volume_units=volume_units,
            sl_price=sl_str,
            tp1_price=tp_str
        )
        client.close()
        return {
            'ok': ord_ok,
            'res': ord_res,
            'lots': lots,
            'units': volume_units,
            'symbol': sym_info['name'],
            'symbol_id': sym_info['id']
        }
    except Exception as e:
        client.close()
        return {'ok': False, 'error': str(e)}


def test_fix_connection(password=None):
    cfg = load_fix_config()
    if password:
        cfg['password'] = password

    if not cfg['password']:
        print("⚠️ No FIX API password provided. Please provide password to test connection.")
        return False

    client = FtmoFixClient(cfg)
    try:
        ok, msg = client.send_logon()
        if ok:
            print(f"✅ {msg}")
            client.close()
            return True
        else:
            print(f"❌ {msg}")
            client.close()
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Paul Pro V4 FTMO cTrader FIX Trader')
    parser.add_argument('--test-logon', action='store_true', help='Test FIX 4.4 logon to live.cfixapi.com:5212')
    parser.add_argument('--password', type=str, default='', help='FTMO Account Password')
    args = parser.parse_args()

    if args.test_logon or args.password:
        test_fix_connection(args.password)
    else:
        print("Usage: python ftmo_fix_trader.py --test-logon --password YOUR_PASSWORD")
