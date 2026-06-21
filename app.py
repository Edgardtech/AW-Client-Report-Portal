from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import sqlite3, json, os
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import HexColor
import io

app = Flask(__name__)
app.secret_key = 'aw-portal-secret-2026'
DB = 'portal.db'

USERS = {'admin': 'windbrook2026', 'rebecca': 'windbrook2026', 'maryann': 'windbrook2026'}

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name1 TEXT NOT NULL,
            name2 TEXT,
            dob1 TEXT,
            dob2 TEXT,
            ssn1 TEXT,
            ssn2 TEXT,
            monthly_salary REAL,
            monthly_expense REAL,
            insurance_deductibles REAL DEFAULT 0,
            private_reserve_target REAL,
            accounts TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            quarter TEXT,
            year INTEGER,
            data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );
    ''')
    db.commit()
    db.close()

def calc_age(dob_str):
    if not dob_str:
        return ''
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except:
        return ''

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('clients'))

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u, p = request.form.get('username',''), request.form.get('password','')
        if USERS.get(u) == p:
            session['user'] = u
            return redirect(url_for('clients'))
        error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/clients')
def clients():
    if 'user' not in session: return redirect(url_for('login'))
    db = get_db()
    rows = db.execute('''
        SELECT c.*, MAX(r.created_at) as last_report
        FROM clients c LEFT JOIN reports r ON r.client_id=c.id
        GROUP BY c.id ORDER BY c.name1
    ''').fetchall()
    db.close()
    return render_template('clients.html', clients=rows)

@app.route('/clients/new', methods=['GET','POST'])
def new_client():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        f = request.form
        accounts = json.loads(f.get('accounts_json', '[]'))
        db = get_db()
        db.execute('''INSERT INTO clients
            (name1,name2,dob1,dob2,ssn1,ssn2,monthly_salary,monthly_expense,insurance_deductibles,accounts)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (f['name1'], f.get('name2',''), f.get('dob1',''), f.get('dob2',''),
             f.get('ssn1',''), f.get('ssn2',''),
             float(f.get('monthly_salary',0)), float(f.get('monthly_expense',0)),
             float(f.get('insurance_deductibles',0)),
             json.dumps(accounts)))
        db.commit()
        db.close()
        return redirect(url_for('clients'))
    return render_template('client_form.html', client=None)

@app.route('/clients/<int:cid>/edit', methods=['GET','POST'])
def edit_client(cid):
    if 'user' not in session: return redirect(url_for('login'))
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id=?', (cid,)).fetchone()
    if request.method == 'POST':
        f = request.form
        accounts = json.loads(f.get('accounts_json', '[]'))
        db.execute('''UPDATE clients SET
            name1=?,name2=?,dob1=?,dob2=?,ssn1=?,ssn2=?,
            monthly_salary=?,monthly_expense=?,insurance_deductibles=?,accounts=?
            WHERE id=?''',
            (f['name1'], f.get('name2',''), f.get('dob1',''), f.get('dob2',''),
             f.get('ssn1',''), f.get('ssn2',''),
             float(f.get('monthly_salary',0)), float(f.get('monthly_expense',0)),
             float(f.get('insurance_deductibles',0)),
             json.dumps(accounts), cid))
        db.commit()
        db.close()
        return redirect(url_for('clients'))
    db.close()
    return render_template('client_form.html', client=client)

@app.route('/clients/<int:cid>/report', methods=['GET','POST'])
def generate_report(cid):
    if 'user' not in session: return redirect(url_for('login'))
    db = get_db()
    client = db.execute('SELECT * FROM clients WHERE id=?', (cid,)).fetchone()
    last_report = db.execute('SELECT * FROM reports WHERE client_id=? ORDER BY created_at DESC LIMIT 1', (cid,)).fetchone()
    last_data = json.loads(last_report['data']) if last_report else {}

    accounts = json.loads(client['accounts'])

    if request.method == 'POST':
        f = request.form
        balances = {}
        for acc in accounts:
            key = f'bal_{acc["id"]}'
            balances[acc['id']] = float(f.get(key, 0))

        private_reserve_bal = float(f.get('private_reserve_balance', 0))
        zillow_value = float(f.get('zillow_value', 0))

        inflow = client['monthly_salary']
        outflow = client['monthly_expense']
        excess = inflow - outflow
        pr_target = (6 * outflow) + client['insurance_deductibles']

        ret1 = sum(balances.get(a['id'],0) for a in accounts if a['type']=='retirement' and a['owner']=='1')
        ret2 = sum(balances.get(a['id'],0) for a in accounts if a['type']=='retirement' and a['owner']=='2')
        non_ret = sum(balances.get(a['id'],0) for a in accounts if a['type']=='non-retirement')
        liabilities = sum(balances.get(a['id'],0) for a in accounts if a['type']=='liability')
        grand_total = ret1 + ret2 + non_ret + zillow_value

        data = {
            'inflow': inflow, 'outflow': outflow, 'excess': excess,
            'private_reserve_balance': private_reserve_bal,
            'private_reserve_target': pr_target,
            'zillow_value': zillow_value,
            'balances': balances,
            'ret1': ret1, 'ret2': ret2, 'non_ret': non_ret,
            'liabilities': liabilities, 'grand_total': grand_total,
            'quarter': f.get('quarter'), 'year': int(f.get('year', date.today().year))
        }

        db.execute('INSERT INTO reports (client_id,quarter,year,data) VALUES (?,?,?,?)',
                   (cid, data['quarter'], data['year'], json.dumps(data)))
        db.commit()
        report_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()
        return redirect(url_for('report_view', cid=cid, rid=report_id))

    db.close()
    current_year = date.today().year
    quarters = ['Q1','Q2','Q3','Q4']
    return render_template('report_form.html', client=client, accounts=accounts,
                           last_data=last_data, current_year=current_year, quarters=quarters,
                           calc_age=calc_age)

@app.route('/clients/<int:cid>/reports/<int:rid>')
def report_view(cid, rid):
    if 'user' not in session: return redirect(url_for('login'))
    db = get_db()
    client = dict(db.execute('SELECT * FROM clients WHERE id=?', (cid,)).fetchone())
    report = dict(db.execute('SELECT * FROM reports WHERE id=? AND client_id=?', (rid,cid)).fetchone())
    db.close()
    data = json.loads(report['data'])
    accounts = json.loads(client['accounts'])
    return render_template('report_view.html', client=client, report=report, data=data, accounts=accounts, calc_age=calc_age)

@app.route('/clients/<int:cid>/reports/<int:rid>/pdf/<report_type>')
def download_pdf(cid, rid, report_type):
    if 'user' not in session: return redirect(url_for('login'))
    db = get_db()
    client = dict(db.execute('SELECT * FROM clients WHERE id=?', (cid,)).fetchone())
    report = dict(db.execute('SELECT * FROM reports WHERE id=?', (rid,)).fetchone())
    db.close()
    data = json.loads(report['data'])
    accounts = json.loads(client['accounts'])

    buf = io.BytesIO()
    if report_type == 'sacs':
        generate_sacs_pdf(buf, client, data, report)
    else:
        generate_tcc_pdf(buf, client, data, accounts, report)
    buf.seek(0)
    fname = f"{client['name1'].replace(' ','_')}_{report_type.upper()}_{data['quarter']}{data['year']}.pdf"
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)

# ─── PDF GENERATION ────────────────────────────────────────────────

def fmt(n):
    return f"${n:,.0f}"

def generate_sacs_pdf(buf, client, data, report):
    c = rl_canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Colors
    BLUE_DARK = HexColor('#1B3A6B')
    BLUE_MID  = HexColor('#2E5FA3')
    GREEN     = HexColor('#2E7D32')
    RED       = HexColor('#C62828')
    BLUE_LIGHT= HexColor('#1565C0')
    GRAY      = HexColor('#F5F5F5')
    WHITE     = colors.white

    # Header bar
    c.setFillColor(BLUE_DARK)
    c.rect(0, H-80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 22)
    c.drawString(40, H-42, 'Windbrook Solutions')
    c.setFont('Helvetica', 11)
    c.drawRightString(W-40, H-35, f"Simple Automated Cash Flow System (SACS)")
    c.drawRightString(W-40, H-52, f"{data['quarter']} {data['year']}")

    # Client name
    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, H-110, client['name1'] + (f" & {client['name2']}" if client.get('name2') else ''))

    # ── Three bubbles ──
    cy = H - 280
    # Inflow bubble
    c.setFillColor(GREEN)
    c.circle(130, cy, 90, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(130, cy+30, 'INFLOW')
    c.setFont('Helvetica', 9)
    c.drawCentredString(130, cy+14, 'Monthly Salary')
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(130, cy-8, fmt(data['inflow']))
    c.setFont('Helvetica', 8)
    c.drawCentredString(130, cy-26, 'per month')

    # Arrow inflow → outflow (red X arrow)
    c.setStrokeColor(RED)
    c.setLineWidth(2.5)
    c.line(222, cy, 308, cy)
    c.setFillColor(RED)
    # arrowhead
    p = c.beginPath()
    p.moveTo(308, cy)
    p.lineTo(300, cy+5)
    p.lineTo(300, cy-5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    # X mark on arrow
    c.setStrokeColor(RED)
    c.setLineWidth(1.5)
    c.line(255, cy-8, 268, cy+8)
    c.line(255, cy+8, 268, cy-8)

    # Outflow bubble
    c.setFillColor(RED)
    c.circle(400, cy, 90, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(400, cy+30, 'OUTFLOW')
    c.setFont('Helvetica', 9)
    c.drawCentredString(400, cy+14, 'Monthly Expenses')
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(400, cy-8, fmt(data['outflow']))
    c.setFont('Helvetica', 8)
    c.drawCentredString(400, cy-26, 'per month')

    # Arrow outflow → private reserve (blue)
    c.setStrokeColor(BLUE_MID)
    c.setLineWidth(2.5)
    c.line(492, cy, 578, cy)
    p2 = c.beginPath()
    p2.moveTo(578, cy)
    p2.lineTo(570, cy+5)
    p2.lineTo(570, cy-5)
    p2.close()
    c.drawPath(p2, fill=1, stroke=0)
    # label above arrow
    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(535, cy+12, fmt(data['excess']))
    c.setFont('Helvetica', 7)
    c.drawCentredString(535, cy-2, 'excess/month')

    # Private Reserve box
    c.setFillColor(BLUE_LIGHT)
    c.roundRect(580, cy-70, 155, 140, 12, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(657, cy+45, 'PRIVATE')
    c.drawCentredString(657, cy+31, 'RESERVE')
    c.setFont('Helvetica', 8)
    c.drawCentredString(657, cy+14, 'High-Yield Savings')
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.5)
    c.line(600, cy+5, 715, cy+5)
    c.setFont('Helvetica', 8)
    c.drawCentredString(657, cy-8, 'Current Balance')
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(657, cy-26, fmt(data['private_reserve_balance']))
    c.setFont('Helvetica', 7)
    c.drawCentredString(657, cy-42, f"Target: {fmt(data['private_reserve_target'])}")

    # ── Summary strip ──
    sy = cy - 160
    c.setFillColor(GRAY)
    c.roundRect(30, sy-30, W-60, 70, 8, fill=1, stroke=0)
    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 10)
    cols = [
        ('Monthly Inflow', fmt(data['inflow'])),
        ('Monthly Outflow', fmt(data['outflow'])),
        ('Monthly Excess', fmt(data['excess'])),
        ('PR Target', fmt(data['private_reserve_target'])),
    ]
    for i,(label,val) in enumerate(cols):
        x = 80 + i*155
        c.setFont('Helvetica', 8)
        c.drawCentredString(x, sy+18, label)
        c.setFont('Helvetica-Bold', 12)
        c.drawCentredString(x, sy, val)

    # Footer
    c.setFillColor(BLUE_DARK)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica', 8)
    c.drawCentredString(W/2, 10, f'Windbrook Solutions — Confidential — Generated {datetime.now().strftime("%B %d, %Y")}')

    c.save()

def generate_tcc_pdf(buf, client, data, accounts, report):
    c = rl_canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    BLUE_DARK  = HexColor('#1B3A6B')
    BLUE_MID   = HexColor('#2E5FA3')
    GREEN_DARK = HexColor('#1B5E20')
    GREEN      = HexColor('#388E3C')
    GRAY_BOX   = HexColor('#EEEEEE')
    GRAY_DARK  = HexColor('#757575')
    RED        = HexColor('#C62828')
    WHITE      = colors.white

    # Header
    c.setFillColor(BLUE_DARK)
    c.rect(0, H-80, W, 80, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 22)
    c.drawString(40, H-42, 'Windbrook Solutions')
    c.setFont('Helvetica', 11)
    c.drawRightString(W-40, H-35, 'Total Client Chart (TCC)')
    c.drawRightString(W-40, H-52, f"{data['quarter']} {data['year']}")

    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 15)
    c.drawString(40, H-108, client['name1'] + (f" & {client['name2']}" if client.get('name2') else ''))

    def bubble(cx, cy, r, fill_color, title, subtitle, amount, note=''):
        c.setFillColor(fill_color)
        c.circle(cx, cy, r, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(cx, cy+r*0.45, title)
        if subtitle:
            c.setFont('Helvetica', 7)
            c.drawCentredString(cx, cy+r*0.18, subtitle)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(cx, cy-r*0.1, fmt(amount))
        if note:
            c.setFont('Helvetica', 6)
            c.drawCentredString(cx, cy-r*0.38, note)

    def gray_box(x, y, w, h, label, amount):
        c.setFillColor(GRAY_BOX)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=0)
        c.setFillColor(BLUE_DARK)
        c.setFont('Helvetica', 7)
        c.drawCentredString(x+w/2, y+h-14, label)
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(x+w/2, y+8, fmt(amount))

    balances = data.get('balances', {})

    # ── RETIREMENT accounts ──
    ret1_accs = [a for a in accounts if a['type']=='retirement' and a['owner']=='1']
    ret2_accs = [a for a in accounts if a['type']=='retirement' and a['owner']=='2']

    # Client 1 retirement row
    label1 = client['name1'].split()[0] + ' — Retirement'
    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(30, H-138, label1)

    bx = 30
    for a in ret1_accs:
        bal = float(balances.get(a['id'], 0))
        bubble(bx+35, H-190, 35, GREEN, a['subtype'], f"****{a.get('last4','')}", bal)
        bx += 85
    gray_box(bx+5, H-215, 100, 50, f"{client['name1'].split()[0]} Retirement Total", data['ret1'])

    # Client 2 retirement row
    if client.get('name2') and ret2_accs:
        label2 = client['name2'].split()[0] + ' — Retirement'
        c.setFillColor(BLUE_DARK)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(30, H-258, label2)
        bx2 = 30
        for a in ret2_accs:
            bal = float(balances.get(a['id'], 0))
            bubble(bx2+35, H-310, 35, GREEN, a['subtype'], f"****{a.get('last4','')}", bal)
            bx2 += 85
        gray_box(bx2+5, H-335, 100, 50, f"{client['name2'].split()[0]} Retirement Total", data['ret2'])

    # ── NON-RETIREMENT ──
    nr_accs = [a for a in accounts if a['type']=='non-retirement']
    y_nr = H - 380
    c.setFillColor(BLUE_DARK)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(30, y_nr+20, 'Non-Retirement Accounts')
    bx3 = 30
    for a in nr_accs:
        bal = float(balances.get(a['id'], 0))
        bubble(bx3+35, y_nr-35, 35, BLUE_MID, a['subtype'], f"****{a.get('last4','')}", bal)
        bx3 += 85
    gray_box(bx3+5, y_nr-60, 105, 50, 'Non-Retirement Total', data['non_ret'])

    # ── TRUST ──
    trust_accs = [a for a in accounts if a['type']=='trust']
    y_tr = y_nr - 120
    if trust_accs or data.get('zillow_value',0):
        c.setFillColor(BLUE_DARK)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(30, y_tr+20, 'Trust / Property')
        c.setFillColor(HexColor('#6A1B9A'))
        c.circle(75, y_tr-30, 35, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(75, y_tr-18, 'TRUST')
        c.setFont('Helvetica', 7)
        c.drawCentredString(75, y_tr-32, 'Zillow Est.')
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(75, y_tr-46, fmt(data.get('zillow_value',0)))

    # ── LIABILITIES ──
    liab_accs = [a for a in accounts if a['type']=='liability']
    y_lb = y_tr - 110
    c.setFillColor(RED)
    c.roundRect(30, y_lb-40, W-60, 80, 8, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(50, y_lb+22, 'LIABILITIES')
    lx = 50
    for a in liab_accs:
        bal = float(balances.get(a['id'], 0))
        c.setFont('Helvetica', 8)
        c.drawString(lx, y_lb+5, f"{a['subtype']}: {fmt(bal)}")
        if a.get('rate'):
            c.setFont('Helvetica', 7)
            c.drawString(lx, y_lb-8, f"Rate: {a['rate']}%")
        lx += 140
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(W-50, y_lb+5, f"Total: {fmt(data['liabilities'])}")

    # ── GRAND TOTAL ──
    c.setFillColor(BLUE_DARK)
    c.roundRect(30, y_lb-100, W-60, 50, 8, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, y_lb-68, 'TOTAL NET WORTH (excl. liabilities)')
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(W/2, y_lb-90, fmt(data['grand_total']))

    # Footer
    c.setFillColor(BLUE_DARK)
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica', 8)
    c.drawCentredString(W/2, 10, f'Windbrook Solutions — Confidential — Generated {datetime.now().strftime("%B %d, %Y")}')

    c.save()

# Auto-init DB on startup (Railway + local)
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
