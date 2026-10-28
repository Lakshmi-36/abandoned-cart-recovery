"""Intermediate Abandoned Cart Recovery dashboard. Read-only MySQL queries only."""
import os
import mysql.connector
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Recovery Control Center",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* Clearly visible dropdowns */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label {
    color: #10243a !important;
    font-weight: 750 !important;
}

/* Teal background makes filters easy to identify */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color: #e6fffb !important;
    border: 2px solid #0d9488 !important;
    border-radius: 10px !important;
    min-height: 44px !important;
}

/* Stronger highlight when clicked */
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
    background-color: #ccfbf1 !important;
    border: 2px solid #115e59 !important;
    box-shadow: 0 0 0 4px rgba(13, 148, 136, 0.25) !important;
}

/* Selected value */
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMultiSelect"] [data-baseweb="select"] * {
    color: #134e4a !important;
    font-weight: 650 !important;
}

/* Selected menu option */
[data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background-color: #99f6e4 !important;
    color: #134e4a !important;
    font-weight: 700 !important;
}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --navy: #14253f;
    --navy-light: #203a5c;
    --blue: #4776e6;
    --teal: #17a995;
    --green: #1c9c72;
    --purple: #8064d8;
    --orange: #e6a23c;
    --page: #f5f7fb;
    --card: #ffffff;
    --text: #18283f;
    --muted: #78879b;
    --border: #e7ecf3;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: var(--page);
    color: var(--text);
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: var(--navy);
    border-right: 1px solid #263c58;
}

[data-testid="stSidebar"] * {
    color: #e8eef7;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #aebdd0;
}

[data-testid="stSidebar"] hr {
    border-color: #344761;
}

[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 7px;
}

[data-testid="stSidebar"] [role="radiogroup"] label {
    background: transparent;
    border-radius: 9px;
    padding: 10px 12px;
    transition: background .2s ease;
}

[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: #263d5a;
}

[data-testid="stSidebar"] [role="radiogroup"] label p {
    font-size: 13px;
    font-weight: 500;
}

.block-container {
    padding-top: 1.7rem;
    padding-bottom: 3rem;
    max-width: 1600px;
}

h1, h2, h3 {
    color: var(--text);
    letter-spacing: -0.6px;
}

h1 {
    font-size: 29px !important;
    font-weight: 800 !important;
}

h2 {
    font-size: 23px !important;
    font-weight: 750 !important;
}

h3 {
    font-size: 17px !important;
    font-weight: 700 !important;
}

[data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 19px 20px;
    box-shadow: 0 3px 12px rgba(24, 40, 63, .035);
}

[data-testid="stMetricLabel"] {
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .7px;
}

[data-testid="stMetricValue"] {
    color: var(--navy);
    font-size: 26px;
    font-weight: 800;
}

[data-testid="stMetricDelta"] {
    font-size: 12px;
}

[data-testid="stPlotlyChart"],
[data-testid="stDataFrame"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 8px;
    box-shadow: 0 3px 12px rgba(24, 40, 63, .025);
}

[data-testid="stSelectbox"],
[data-testid="stTextInput"] {
    background: white;
    border-radius: 9px;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 8px;
    font-weight: 600;
}

[data-testid="stAlert"] {
    border-radius: 10px;
}

hr {
    border-color: var(--border);
}

.small-label {
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .8px;
    text-transform: uppercase;
}

.section-heading {
    color: var(--navy);
    font-size: 19px;
    font-weight: 750;
    margin: 22px 0 5px;
}

.hero {
    background: white;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 23px 27px;
    margin: 0 0 22px;
    box-shadow: 0 4px 18px rgba(24, 40, 63, .035);
}

.hero h1 {
    margin: 0 0 6px;
}

.hero p {
    color: var(--muted);
    margin: 0;
    font-size: 13px;
}

@media (max-width: 900px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 21px;
    }
}
</style>
""", unsafe_allow_html=True)
# Load private settings from the local .env file.
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

if os.path.isfile(env_path):
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(
                    key.strip(),
                    value.strip().strip('"').strip("'")
                )

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_NAME = os.getenv("DB_NAME", "abandoned_cart_full_db")
TABLES=['customers','consent_events','sessions','carts','cart_lines','cart_events','campaigns','message_templates','campaign_templates','campaign_carts','send_attempts','message_events','orders','order_lines','order_events','attributions']

def q(conn, sql, params=None):
    if not sql.lstrip().upper().startswith(('SELECT','WITH','SHOW','DESCRIBE')):
        raise ValueError('Read-only dashboard: only SELECT queries are permitted.')
    return pd.read_sql_query(sql, conn, params=params)
def n(v):
    try:return f'{int(v or 0):,}'
    except (ValueError,TypeError):return '0'
def money(v):
    try:return f'₹{float(v or 0):,.2f}'
    except (ValueError,TypeError):return '₹0.00'
def chart(fig):
    fig.update_layout(paper_bgcolor='white',plot_bgcolor='white',font=dict(family='Inter',color='#263a52'),margin=dict(l=15,r=15,t=55,b=15),legend_title_text='')
    return fig
def table(df, key, filename):
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button('Export CSV',df.to_csv(index=False).encode('utf-8-sig'),filename,'text/csv',key=key)
def active_filter(text):
    st.markdown(
        f'<div style="background:#ccfbf1; border:1px solid #0d9488; '
        f'border-left:5px solid #0d9488; padding:12px 15px; '
        f'border-radius:9px; color:#115e59; font-weight:700; '
        f'margin:8px 0 14px;">ACTIVE FILTERS: {text}</div>',
        unsafe_allow_html=True
    )
st.sidebar.markdown('# RECOVERY / OPS')
st.sidebar.caption('ABANDONED CART CONTROL CENTER')
page=st.sidebar.radio('NAVIGATION',['Control Center','Cart Lifecycle','Campaign Workspace','Consent Audit','Business Rules & Data Quality','Table Explorer'])
st.sidebar.divider(); st.sidebar.caption('Read-only connection'); st.sidebar.code(DB_NAME)
pwd = os.getenv("DB_PASSWORD", "")
st.markdown('<div class="hero"><h1>Recovery Control Center</h1><p>Operational view · live MySQL data · read-only monitoring</p></div>',unsafe_allow_html=True)
if not pwd:
    st.error("DB_PASSWORD is missing from your local .env file.")
    st.stop()
try:
    conn=mysql.connector.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,password=pwd,database=DB_NAME,connection_timeout=8,autocommit=True)
    current=q(conn,'SELECT DATABASE()').iloc[0,0]
    if current != DB_NAME:
        st.error(f'Safety check failed: connected to {current}, expected {DB_NAME}.'); st.stop()
except Exception as e:
    st.error('Could not connect to MySQL. Check server, username, password and database name.')
    st.caption(f'Technical detail: {type(e).__name__}: {e}'); st.stop()

summary=q(conn,"""SELECT
(SELECT COUNT(*) FROM customers) customers,
(SELECT COUNT(*) FROM carts) carts,
(SELECT COUNT(*) FROM carts WHERE cart_status='ABANDONED') abandoned,
(SELECT COUNT(*) FROM carts WHERE cart_status='ACTIVE') active,
(SELECT COUNT(*) FROM send_attempts WHERE send_status='SENT') sent,
(SELECT COUNT(*) FROM send_attempts WHERE send_status='SUPPRESSED') suppressed,
(SELECT COUNT(*) FROM orders WHERE order_status='PAID') paid_orders,
(SELECT COALESCE(SUM(order_total),0) FROM orders WHERE order_status='PAID') paid_revenue,
(SELECT COUNT(*) FROM attributions WHERE attribution_status='CREDITED') credited,
(SELECT COALESCE(SUM(credited_revenue),0) FROM attributions WHERE attribution_status='CREDITED') attributed_revenue""").iloc[0]

if page=='Control Center':
    st.subheader('Operations at a glance')
    st.caption('Use this screen to spot where recovery flow is losing volume. Paid orders and verified credited attribution are shown separately.')
    abandonment_rate = (
        summary.abandoned / summary.carts * 100
        if summary.carts else 0
    )

    kpis = [
        ('TOTAL CARTS', n(summary.carts)),
        ('ABANDONED CARTS', n(summary.abandoned)),
        ('ABANDONMENT RATE', f'{abandonment_rate:.1f}%'),
        ('MESSAGES SENT', n(summary.sent)),
        ('PAID ORDERS', n(summary.paid_orders)),
        ('ATTRIBUTED REVENUE', money(summary.attributed_revenue)),
    ]
    cols=st.columns(6)
    for col,(label,value) in zip(cols,kpis): col.metric(label,value)
    st.markdown("### What the data is telling us")

    st.info(
        f"{n(summary.abandoned)} out of {n(summary.carts)} carts "
        f"are marked abandoned ({abandonment_rate:.1f}%). "
        "This identifies the current abandoned-cart opportunity, "
        "but it does not prove how many carts can be recovered."
    )

    st.caption(
        "Paid orders, messages sent and campaign-attributed revenue "
        "are different measures. The available data does not prove "
        "that every paid order resulted from a recovery message."
    )
    st.markdown('### Recovery journey')
    funnel=pd.DataFrame({'stage':['All carts','Abandoned carts','Messages sent','Paid orders','Credited attributions'],'records':[int(summary.carts),int(summary.abandoned),int(summary.sent),int(summary.paid_orders),int(summary.credited)]})
    left,right=st.columns([1.6,1])
    left.plotly_chart(chart(px.funnel(funnel,x='records',y='stage',title='Volume at each stage')),use_container_width=True)
    right.markdown('#### Revenue snapshot')
    right.metric('Paid order revenue',money(summary.paid_revenue))
    right.metric('Credited attribution revenue',money(summary.attributed_revenue))
    right.caption('These revenue values have different definitions and should not be added together.')
    st.markdown('### Channel operations')
    ch=q(conn,"SELECT channel,SUM(send_status='SENT') sent,SUM(send_status='SUPPRESSED') suppressed FROM send_attempts GROUP BY channel")
    left,right=st.columns([1.2,1])
    left.plotly_chart(chart(px.bar(ch.melt(id_vars='channel',var_name='outcome',value_name='count'),x='channel',y='count',color='outcome',barmode='group',title='Sent vs suppressed by channel',text_auto=True)),use_container_width=True)
    cs=q(conn,'SELECT cart_status status,COUNT(*) records FROM carts GROUP BY cart_status')
    right.plotly_chart(chart(px.pie(cs,names='status',values='records',hole=.58,title='Current cart states')),use_container_width=True)
    st.info('The funnel is a volume comparison, not a claim that each paid order came from an abandoned cart. Recovery attribution should be verified separately.')

elif page=='Cart Lifecycle':
    st.subheader('Abandoned cart analysis'); st.caption('Cart status, amounts, lifecycle timestamps and item-level details.')
    a,b,c=st.columns(3)
    statuses=q(conn,'SELECT DISTINCT cart_status FROM carts ORDER BY cart_status').cart_status.dropna().tolist()
    status=a.selectbox('Status',['All']+statuses); cart_search=b.text_input('Cart ID contains'); customer_search=c.text_input('Customer ID contains')
    active_filter(
    f"Status: {status} | Cart ID: {cart_search or 'Any'} | "
    f"Customer ID: {customer_search or 'Any'}"
    )
    clauses=[]; params=[]
    if status!='All': clauses.append('c.cart_status=%s'); params.append(status)
    if cart_search.strip(): clauses.append('c.cart_id LIKE %s'); params.append('%'+cart_search.strip()+'%')
    if customer_search.strip(): clauses.append('c.customer_id LIKE %s'); params.append('%'+customer_search.strip()+'%')
    where='WHERE '+' AND '.join(clauses) if clauses else ''
    carts=q(conn,f"""SELECT c.cart_id,c.customer_id,c.cart_status,c.currency,c.cart_total,c.created_at,c.last_activity_at,c.abandoned_at,c.recovered_at,
    COUNT(DISTINCT CASE WHEN l.line_status='ACTIVE' THEN l.cart_line_id END) active_lines,
    COALESCE(SUM(CASE WHEN l.line_status='ACTIVE' THEN l.quantity ELSE 0 END),0) active_units
    FROM carts c LEFT JOIN cart_lines l ON l.cart_id=c.cart_id {where}
    GROUP BY c.cart_id,c.customer_id,c.cart_status,c.currency,c.cart_total,c.created_at,c.last_activity_at,c.abandoned_at,c.recovered_at
    ORDER BY c.last_activity_at DESC LIMIT 2000""",params)
    st.caption('Maximum 2,000 matching carts per view.'); table(carts,'cart_export','cart_analysis.csv')
    if not carts.empty:
        chosen=st.selectbox('Inspect cart',carts.cart_id.tolist())
        lines=q(conn,'SELECT cart_line_id,product_sku,product_name,quantity,unit_price,line_total,line_status,added_at,updated_at,removed_at FROM cart_lines WHERE cart_id=%s ORDER BY cart_line_id',[chosen])
        st.markdown(f'#### Items in `{chosen}`'); table(lines,'line_export','selected_cart_lines.csv')
    st.markdown('#### 24-hour abandonment rule')
    issues=q(conn,"""SELECT cart_id,last_activity_at,abandoned_at,TIMESTAMPDIFF(HOUR,last_activity_at,abandoned_at) inactive_hours FROM carts
    WHERE cart_status='ABANDONED' AND (abandoned_at IS NULL OR last_activity_at IS NULL OR abandoned_at<DATE_ADD(last_activity_at,INTERVAL 24 HOUR)) LIMIT 1000""")
    if issues.empty: st.success('PASS: no abandoned-cart timing violations found by this check.')
    else: st.error(f'{len(issues)} possible timing issues found (up to 1,000 shown).'); table(issues,'timing_export','abandonment_timing_issues.csv')

elif page=='Campaign Workspace':
    st.subheader('Campaign performance'); st.caption('Campaign-level sends, suppressions and recorded message events.')
    data=q(conn,"""SELECT c.campaign_id,c.campaign_name,c.channel,c.campaign_variant,c.objective,c.campaign_status,c.attribution_window_hours,
    COUNT(DISTINCT cc.campaign_cart_id) enrolled_records,
    COUNT(DISTINCT CASE WHEN s.send_status='SENT' THEN s.send_id END) sent_messages,
    COUNT(DISTINCT CASE WHEN s.send_status='SUPPRESSED' THEN s.send_id END) suppressed_messages
    FROM campaigns c LEFT JOIN campaign_carts cc ON cc.campaign_id=c.campaign_id LEFT JOIN send_attempts s ON s.campaign_cart_id=cc.campaign_cart_id
    GROUP BY c.campaign_id,c.campaign_name,c.channel,c.campaign_variant,c.objective,c.campaign_status,c.attribution_window_hours
    ORDER BY sent_messages DESC LIMIT 2000""")
    if not data.empty:
        a,b=st.columns(2)
        a.plotly_chart(chart(px.bar(data.groupby('channel',dropna=False)[['sent_messages','suppressed_messages']].sum().reset_index().melt(id_vars='channel',var_name='outcome',value_name='messages'),x='channel',y='messages',color='outcome',barmode='group',title='Messages by channel',text_auto=True)),use_container_width=True)
        b.plotly_chart(chart(px.bar(data.groupby('campaign_variant',dropna=False)['sent_messages'].sum().reset_index(),x='campaign_variant',y='sent_messages',title='Sent messages by variant',text_auto=True)),use_container_width=True)
    table(data,'campaign_export','campaign_performance.csv')
    ev=q(conn,'SELECT event_type,COUNT(*) event_count,MIN(event_at) first_event,MAX(event_at) latest_event FROM message_events GROUP BY event_type ORDER BY event_count DESC')
    st.markdown('#### Message event funnel evidence'); st.caption('Delivery/open/click rates should only be calculated when the corresponding event types exist and the denominator is defined.')
    if not ev.empty: st.plotly_chart(chart(px.bar(ev,x='event_type',y='event_count',title='Recorded message-event counts',text_auto=True)),use_container_width=True)
    table(ev,'events_export','message_event_summary.csv')

elif page=='Consent Audit':
    st.subheader('Consent & suppression audit'); st.caption('Latest consent at send time and the rolling seven-day channel frequency cap.')
    opt=q(conn,"""SELECT s.send_id,s.customer_id,s.channel,s.attempted_at,
    (SELECT ce.consent_status FROM consent_events ce WHERE ce.customer_id=s.customer_id AND ce.channel=s.channel AND ce.effective_at<=s.attempted_at ORDER BY ce.effective_at DESC,ce.consent_event_id DESC LIMIT 1) consent_at_send
    FROM send_attempts s WHERE s.send_status='SENT' AND COALESCE((SELECT ce.consent_status FROM consent_events ce WHERE ce.customer_id=s.customer_id AND ce.channel=s.channel AND ce.effective_at<=s.attempted_at ORDER BY ce.effective_at DESC,ce.consent_event_id DESC LIMIT 1),'UNKNOWN')<>'OPTED_IN' ORDER BY s.attempted_at DESC LIMIT 1000""")
    st.markdown('#### Messages sent without latest OPTED_IN consent')
    if opt.empty: st.success('PASS: no sent-message consent violations found.')
    else: st.error(f'{len(opt)} potential consent violations found (up to 1,000 shown).'); table(opt,'optout_export','consent_violations.csv')
    freq=q(conn,"""SELECT s.send_id,s.customer_id,s.channel,s.attempted_at,(SELECT COUNT(*) FROM send_attempts p WHERE p.customer_id=s.customer_id AND p.channel=s.channel AND p.send_status='SENT' AND p.attempted_at>DATE_SUB(s.attempted_at,INTERVAL 7 DAY) AND p.attempted_at<=s.attempted_at) sends_in_rolling_7_days
    FROM send_attempts s WHERE s.send_status='SENT' AND (SELECT COUNT(*) FROM send_attempts p WHERE p.customer_id=s.customer_id AND p.channel=s.channel AND p.send_status='SENT' AND p.attempted_at>DATE_SUB(s.attempted_at,INTERVAL 7 DAY) AND p.attempted_at<=s.attempted_at)>3 ORDER BY s.attempted_at DESC LIMIT 1000""")
    st.markdown('#### Frequency-cap violations');
    if freq.empty: st.success('PASS: no fourth-or-later sent message within a rolling seven-day window found.')
    else: st.error(f'{len(freq)} frequency-cap violations found (up to 1,000 shown).'); table(freq,'freq_export','frequency_cap_issues.csv')
    sup=q(conn,'SELECT send_status,channel,suppression_reason,COUNT(*) record_count FROM send_attempts GROUP BY send_status,channel,suppression_reason ORDER BY record_count DESC')
    st.markdown('#### Suppression summary'); table(sup,'supp_export','send_suppression_summary.csv')

elif page=='Data Quality Lab':
    st.subheader('Attribution & data quality'); st.caption('Live checks for the required anomalies and key reconciliation rules.')
    checks=[]
    def check(name,sql,meaning):
        count=int(q(conn,sql).iloc[0,0]); checks.append({'Check':name,'Issue count':count,'Status':'PASS' if count==0 else 'ISSUES FOUND','Meaning':meaning})
    check('MESSAGE_SENT_AFTER_OPTOUT',"""SELECT COUNT(*) FROM send_attempts s WHERE s.send_status='SENT' AND (SELECT ce.consent_status FROM consent_events ce WHERE ce.customer_id=s.customer_id AND ce.channel=s.channel AND ce.effective_at<=s.attempted_at ORDER BY ce.effective_at DESC,ce.consent_event_id DESC LIMIT 1)='OPTED_OUT'""",'Sent message whose latest consent at send time is opt-out.')
    check('CART_ABANDONED_AFTER_PURCHASE',"SELECT COUNT(*) FROM carts c JOIN orders o ON o.cart_id=c.cart_id WHERE c.abandoned_at>o.ordered_at",'Associated cart abandoned timestamp occurs after order time.')
    check('DUPLICATE_CONVERSION_ATTRIBUTION',"SELECT COUNT(*) FROM (SELECT order_id FROM attributions WHERE attribution_status='CREDITED' GROUP BY order_id HAVING COUNT(*)>1) d",'Orders with multiple credited attribution records.')
    check('STALE_CART_TOTAL_AFTER_QUANTITY_UPDATE',"""SELECT COUNT(*) FROM carts c JOIN (SELECT cart_id,SUM(quantity*unit_price) total FROM cart_lines WHERE line_status='ACTIVE' GROUP BY cart_id) x ON x.cart_id=c.cart_id WHERE ABS(c.cart_total-x.total)>0.01""",'Stored cart total differs from active cart-line arithmetic; carts with no active lines are excluded.')
    check('Order total vs order lines',"SELECT COUNT(*) FROM orders o JOIN (SELECT order_id,SUM(line_total) total FROM order_lines GROUP BY order_id) x ON x.order_id=o.order_id WHERE ABS(o.order_total-x.total)>0.01",'Order header total differs from summed order lines.')
    check('Credited revenue vs order total',"SELECT COUNT(*) FROM attributions a JOIN orders o ON o.order_id=a.order_id WHERE a.attribution_status='CREDITED' AND ABS(a.credited_revenue-o.order_total)>0.01",'Credited revenue differs from linked order total.')
    check('Message event before send',"SELECT COUNT(*) FROM message_events m JOIN send_attempts s ON s.send_id=m.send_id WHERE m.event_at<s.attempted_at",'Message event predates the send attempt.')
    check('Campaign/template channel mismatch',"SELECT COUNT(*) FROM campaigns c JOIN campaign_templates ct ON ct.campaign_id=c.campaign_id JOIN message_templates t ON t.template_id=ct.template_id WHERE c.channel<>t.channel",'Campaign channel differs from assigned template channel.')
    cdf=pd.DataFrame(checks); a,b,c=st.columns(3); a.metric('Checks run',len(cdf)); b.metric('Passed',int((cdf.Status=='PASS').sum())); c.metric('Issues found',int((cdf.Status!='PASS').sum()))
    table(cdf,'checks_export','data_quality_checks.csv')
    st.markdown('#### Attribution model and window'); at=q(conn,"SELECT attribution_status,attribution_model,attribution_window_hours,COUNT(*) records,COALESCE(SUM(credited_revenue),0) revenue FROM attributions GROUP BY attribution_status,attribution_model,attribution_window_hours ORDER BY records DESC")
    table(at,'attr_export','attribution_summary.csv')
    st.warning('Window note: this view reports the recorded attribution_window_hours. Verifying actual click-to-order elapsed time requires a reliable click timestamp/link in the data. It does not infer a click from attributed_at.')

elif page=='Table Explorer':
    st.subheader('Database table explorer'); st.caption('Read-only browser for the project tables, with schema details, bounded previews and CSV export.')
    catalog=q(conn,"SELECT TABLE_NAME table_name,TABLE_ROWS estimated_rows FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",[DB_NAME])
    existing=catalog.table_name.tolist(); allowed=[t for t in TABLES if t in existing]; missing=[t for t in TABLES if t not in existing]
    a,b=st.columns(2); a.metric('Expected project tables found',f'{len(allowed)} / 16'); b.metric('Expected tables missing',len(missing))
    table(catalog,'catalog_export','database_table_catalog.csv')
    if missing: st.warning('Missing expected tables: '+', '.join(missing))
    if allowed:
        selected=st.selectbox('Select table',allowed)
        active_filter(f"Selected table: {selected}")
        structure=q(conn,"SELECT COLUMN_NAME column_name,DATA_TYPE data_type,IS_NULLABLE nullable,COLUMN_KEY key_type,COLUMN_DEFAULT default_value FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",[DB_NAME,selected])
        st.markdown(f'#### Schema: `{selected}`'); table(structure,'schema_export',f'{selected}_schema.csv')
        limit=st.selectbox('Preview row limit',[25,50,100,250,500],index=1)
        preview=q(conn,f'SELECT * FROM `{selected}` LIMIT {int(limit)}')
        st.markdown(f'#### Preview: `{selected}`'); st.caption(f'At most {limit} rows shown; full table is not loaded into the app.'); table(preview,'preview_export',f'{selected}_preview.csv')

elif page == 'Business Rules & Data Quality':
    st.subheader('Business Rules & Data Quality')
    st.caption(
        'Live validation of business rules, data integrity, and revenue attribution.'
    )

    # Every validation below is a read-only SELECT query.
    # A check passes only when its query returns zero violating records.
    validation_checks = [
        {
            'rule': 'Customer ID format',
            'category': 'Data integrity',
            'sql': """
                SELECT customer_id AS bad_record
                FROM customers
                WHERE customer_id NOT REGEXP '^CUS-[0-9]{6}$'
            """,
            'meaning': 'Customer IDs must follow the expected format.'
        },
        {
            'rule': 'Cart ID format',
            'category': 'Data integrity',
            'sql': """
                SELECT cart_id AS bad_record
                FROM carts
                WHERE cart_id NOT REGEXP '^CART-2026-[0-9]{6}$'
            """,
            'meaning': 'Cart IDs must follow the expected format.'
        },
        {
            'rule': 'Campaign ID format',
            'category': 'Data integrity',
            'sql': """
                SELECT campaign_id AS bad_record
                FROM campaigns
                WHERE campaign_id NOT REGEXP '^CMP-2026-[0-9]{6}$'
            """,
            'meaning': 'Campaign IDs must follow the expected format.'
        },
        {
            'rule': 'Send ID format',
            'category': 'Data integrity',
            'sql': """
                SELECT send_id AS bad_record
                FROM send_attempts
                WHERE send_id NOT REGEXP '^SEND-2026-[0-9]{6}$'
            """,
            'meaning': 'Message send IDs must follow the expected format.'
        },
        {
            'rule': 'Order ID format',
            'category': 'Data integrity',
            'sql': """
                SELECT order_id AS bad_record
                FROM orders
                WHERE order_id NOT REGEXP '^ORD-2026-[0-9]{6}$'
            """,
            'meaning': 'Order IDs must follow the expected format.'
        },
        {
            'rule': 'Cart customer relationship',
            'category': 'Referential integrity',
            'sql': """
                SELECT c.cart_id AS bad_record
                FROM carts c
                LEFT JOIN customers cu
                    ON cu.customer_id = c.customer_id
                WHERE cu.customer_id IS NULL
            """,
            'meaning': 'Every cart must reference an existing customer.'
        },
        {
            'rule': 'Cart session relationship',
            'category': 'Referential integrity',
            'sql': """
                SELECT c.cart_id AS bad_record
                FROM carts c
                LEFT JOIN sessions s ON s.session_id = c.session_id
                WHERE c.session_id IS NOT NULL
                  AND s.session_id IS NULL
            """,
            'meaning': 'A populated cart session ID must reference an existing session.'
        },
        {
            'rule': 'Campaign-cart relationships',
            'category': 'Referential integrity',
            'sql': """
                SELECT cc.campaign_cart_id AS bad_record
                FROM campaign_carts cc
                LEFT JOIN campaigns c ON c.campaign_id = cc.campaign_id
                LEFT JOIN carts ca ON ca.cart_id = cc.cart_id
                WHERE c.campaign_id IS NULL OR ca.cart_id IS NULL
            """,
            'meaning': 'Campaign-cart records must reference existing campaigns and carts.'
        },
        {
            'rule': 'Attribution relationships',
            'category': 'Referential integrity',
            'sql': """
                SELECT a.attribution_id AS bad_record
                FROM attributions a
                LEFT JOIN orders o ON o.order_id = a.order_id
                LEFT JOIN campaign_carts cc
                    ON cc.campaign_cart_id = a.campaign_cart_id
                WHERE o.order_id IS NULL
                   OR cc.campaign_cart_id IS NULL
            """,
            'meaning': 'Each attribution must reference an existing order and campaign-cart record.'
        },
        {
            'rule': '24-hour abandonment rule',
            'category': 'Cart lifecycle',
            'sql': """
                SELECT cart_id AS bad_record
                FROM carts
                WHERE cart_status = 'ABANDONED'
                  AND (
                      abandoned_at IS NULL
                      OR abandoned_at < DATE_ADD(
                          last_activity_at, INTERVAL 24 HOUR
                      )
                  )
            """,
            'meaning': 'Abandoned carts should meet the configured 24-hour inactivity rule.'
        },
        {
            'rule': 'Cart lifecycle timestamps',
            'category': 'Cart lifecycle',
            'sql': """
                SELECT cart_id AS bad_record
                FROM carts
                WHERE (cart_status = 'ABANDONED' AND abandoned_at IS NULL)
                   OR (cart_status = 'RECOVERED' AND recovered_at IS NULL)
                   OR (cart_status = 'CLOSED' AND closed_at IS NULL)
                   OR (
                       recovered_at IS NOT NULL
                       AND abandoned_at IS NOT NULL
                       AND recovered_at < abandoned_at
                   )
            """,
            'meaning': 'Cart statuses should have consistent lifecycle timestamps.'
        },
        {
            'rule': 'Abandonment after purchase',
            'category': 'Cart lifecycle',
            'sql': """
                SELECT c.cart_id AS bad_record
                FROM carts c
                JOIN orders o ON o.cart_id = c.cart_id
                WHERE c.abandoned_at > o.ordered_at
            """,
            'meaning': 'Flags carts whose abandonment timestamp occurs after a linked purchase.'
        },
        {
            'rule': 'Cart total reconciliation',
            'category': 'Financial integrity',
            'sql': """
                SELECT c.cart_id AS bad_record
                FROM carts c
                JOIN (
                    SELECT cart_id,
                           SUM(quantity * unit_price) AS calculated_total
                    FROM cart_lines
                    WHERE line_status = 'ACTIVE'
                    GROUP BY cart_id
                ) x ON x.cart_id = c.cart_id
                WHERE ABS(c.cart_total - x.calculated_total) > 0.01
            """,
            'meaning': 'Stored cart totals should match the sum of active cart lines.'
        },
        {
            'rule': 'Consent valid at send time',
            'category': 'Consent compliance',
            'sql': """
                SELECT s.send_id AS bad_record
                FROM send_attempts s
                WHERE s.send_status = 'SENT'
                  AND COALESCE((
                      SELECT ce.consent_status
                      FROM consent_events ce
                      WHERE ce.customer_id = s.customer_id
                        AND ce.channel = s.channel
                        AND ce.effective_at <= s.attempted_at
                      ORDER BY ce.effective_at DESC,
                               ce.consent_event_id DESC
                      LIMIT 1
                  ), 'UNKNOWN') <> 'OPTED_IN'
            """,
            'meaning': 'Sent messages must have a valid latest opt-in at send time.'
        },
        {
            'rule': 'Rolling 7-day message cap',
            'category': 'Consent compliance',
            'sql': """
                SELECT s.send_id AS bad_record
                FROM send_attempts s
                WHERE s.send_status = 'SENT'
                  AND (
                      SELECT COUNT(*)
                      FROM send_attempts p
                      WHERE p.customer_id = s.customer_id
                        AND p.channel = s.channel
                        AND p.send_status = 'SENT'
                        AND p.attempted_at >
                            DATE_SUB(s.attempted_at, INTERVAL 7 DAY)
                        AND p.attempted_at <= s.attempted_at
                  ) > 3
            """,
            'meaning': 'Flags sent messages that exceed three sends per customer/channel in a rolling seven-day window.'
        },
        {
            'rule': 'Campaign-template channel consistency',
            'category': 'Campaign operations',
            'sql': """
                SELECT c.campaign_id AS bad_record
                FROM campaigns c
                JOIN campaign_templates ct
                    ON ct.campaign_id = c.campaign_id
                JOIN message_templates t
                    ON t.template_id = ct.template_id
                WHERE c.channel <> t.channel
            """,
            'meaning': 'Campaign and linked message-template channels should match.'
        },
        {
            'rule': 'Message event chronology',
            'category': 'Messaging integrity',
            'sql': """
                SELECT me.message_event_id AS bad_record
                FROM message_events me
                JOIN send_attempts s ON s.send_id = me.send_id
                WHERE me.event_at < s.attempted_at
            """,
            'meaning': 'Message events should not occur before their associated send attempt.'
        },
        {
            'rule': 'Order total reconciliation',
            'category': 'Financial integrity',
            'sql': """
                SELECT o.order_id AS bad_record
                FROM orders o
                LEFT JOIN (
                    SELECT order_id, SUM(line_total) AS calculated_total
                    FROM order_lines
                    GROUP BY order_id
                ) x ON x.order_id = o.order_id
                WHERE ABS(
                    o.order_total - COALESCE(x.calculated_total, 0.00)
                ) > 0.01
            """,
            'meaning': 'Order totals should match their order-line totals.'
        },
        {
            'rule': 'Attribution window sanity',
            'category': 'Attribution',
            'sql': """
                SELECT a.attribution_id AS bad_record
                FROM attributions a
                JOIN orders o ON o.order_id = a.order_id
                WHERE a.attribution_status = 'CREDITED'
                  AND (
                      a.attribution_window_hours <= 0
                      OR o.ordered_at < a.attributed_at
                      OR TIMESTAMPDIFF(
                          HOUR, a.attributed_at, o.ordered_at
                      ) > a.attribution_window_hours
                  )
            """,
            'meaning': 'Checks recorded attribution timing and configured window. The recorded timestamp is not necessarily the original click time.'
        },
        {
            'rule': 'Duplicate conversion credit',
            'category': 'Attribution',
            'sql': """
                SELECT a.order_id AS bad_record
                FROM attributions a
                WHERE a.attribution_status = 'CREDITED'
                GROUP BY a.order_id
                HAVING COUNT(*) > 1
            """,
            'meaning': 'An order should not receive duplicate credited attribution.'
        },
        {
            'rule': 'Credited revenue reconciliation',
            'category': 'Attribution',
            'sql': """
                SELECT o.order_id AS bad_record
                FROM orders o
                JOIN attributions a ON a.order_id = o.order_id
                GROUP BY o.order_id, o.order_total
                HAVING SUM(
                    CASE WHEN a.attribution_status = 'CREDITED'
                         THEN a.credited_revenue ELSE 0 END
                ) > o.order_total + 0.01
            """,
            'meaning': 'Total credited revenue should not exceed the associated order total.'
        },
    ]

    # Display filters.
    categories = ['All'] + sorted({
        check['category'] for check in validation_checks
    })
    selected_category = st.selectbox(
        'Filter by category',
        categories,
        key='live_validation_category'
    )

    if st.button('Run validations', type='primary', key='run_live_validations'):
        st.session_state['live_validation_results'] = []
        progress = st.progress(0)
        status_text = st.empty()

        for index, check in enumerate(validation_checks):
            status_text.write(
                f"Checking {index + 1}/{len(validation_checks)}: "
                f"{check['rule']}"
            )

            try:
                # Wrap each SELECT in a count query.
                # The inner query returns only violating records.
                count_sql = (
                    "SELECT COUNT(*) AS issue_count FROM ("
                    + check['sql'].strip().rstrip(';')
                    + ") AS validation_rows"
                )

                result = q(conn, count_sql)
                issue_count = int(result.iloc[0]['issue_count'])

                st.session_state['live_validation_results'].append({
                    'Rule': check['rule'],
                    'Category': check['category'],
                    'Status': 'PASS' if issue_count == 0 else 'FAIL',
                    'Affected records': issue_count,
                    'Explanation': check['meaning'],
                    'Error': ''
                })

            except Exception as exc:
                st.session_state['live_validation_results'].append({
                    'Rule': check['rule'],
                    'Category': check['category'],
                    'Status': 'ERROR',
                    'Affected records': None,
                    'Explanation': check['meaning'],
                    'Error': f'{type(exc).__name__}: {exc}'
                })

            progress.progress((index + 1) / len(validation_checks))

        status_text.success('Validation run completed.')
        progress.empty()

    results = st.session_state.get('live_validation_results', [])

    if not results:
        st.info('Select "Run validations" to check the current database.')
    else:
        results_df = pd.DataFrame(results)

        if selected_category != 'All':
            results_df = results_df[
                results_df['Category'] == selected_category
            ]

        total = len(results_df)
        passed = int((results_df['Status'] == 'PASS').sum())
        failed = int((results_df['Status'] == 'FAIL').sum())
        errors = int((results_df['Status'] == 'ERROR').sum())

        k1, k2, k3, k4 = st.columns(4)
        k1.metric('CHECKS DISPLAYED', total)
        k2.metric('PASSED', passed)
        k3.metric('FAILED', failed)
        k4.metric('ERRORS', errors)

        st.markdown('### Validation results')

        st.dataframe(
            results_df[
                ['Rule', 'Category', 'Status', 'Affected records', 'Explanation']
            ],
            use_container_width=True,
            hide_index=True
        )

        failures = results_df[results_df['Status'] == 'FAIL']
        if not failures.empty:
            st.markdown('### Issues requiring review')
            st.dataframe(
                failures[
                    ['Rule', 'Affected records', 'Explanation']
                ],
                use_container_width=True,
                hide_index=True
            )

        errors_df = results_df[results_df['Status'] == 'ERROR']
        if not errors_df.empty:
            st.warning(
                'Some checks could not run. These are errors, not passing checks.'
            )
            st.dataframe(
                errors_df[['Rule', 'Error']],
                use_container_width=True,
                hide_index=True
            )

        st.download_button(
            'Export validation report (CSV)',
            data=results_df.to_csv(index=False).encode('utf-8-sig'),
            file_name='business_rules_validation_report.csv',
            mime='text/csv',
            key='live_validation_export'
        )

        st.caption(
            'PASS means the query found zero matching records. '
            'FAIL means one or more records matched the check. '
            'ERROR means the check could not be executed.'
        )

checks = [
    {
        'Rule': '24-hour abandonment rule',
        'Purpose': 'Checks whether carts are marked abandoned according to the configured inactivity period.',
        'Validation': 'Requires cart activity timestamps and the abandonment timestamp or equivalent lifecycle evidence.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': '168-hour attribution window',
        'Purpose': 'Checks whether attributed orders fall within seven days of the relevant campaign click.',
        'Validation': 'Requires a linked click timestamp and order timestamp.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Maximum 3 messages per channel in a rolling 7-day window',
        'Purpose': 'Identifies customers receiving more than three sent messages on the same channel within any rolling seven-day period.',
        'Validation': 'Counts SENT messages by customer, channel, and send timestamp.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Consent valid at send time',
        'Purpose': 'Checks whether a message was sent when the customer had valid consent for that channel.',
        'Validation': 'Compares send timestamps with the applicable consent history.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'LAST_CLICK attribution',
        'Purpose': 'Checks whether credited conversions follow the configured last-click attribution model.',
        'Validation': 'Requires linked click and conversion records, including timestamps.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Prevent duplicate conversion credit',
        'Purpose': 'Identifies orders receiving credit from multiple attribution records.',
        'Validation': 'Counts CREDITED attribution records for each order.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'MESSAGE_SENT_AFTER_OPTOUT',
        'Purpose': 'Identifies messages sent after a customer opted out of the relevant channel.',
        'Validation': 'Compares message-send timestamps with effective opt-out events.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'CART_ABANDONED_AFTER_PURCHASE',
        'Purpose': 'Identifies carts marked abandoned after a related purchase.',
        'Validation': 'Requires reliable links between carts and orders and their timestamps.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'DUPLICATE_CONVERSION_ATTRIBUTION',
        'Purpose': 'Identifies duplicate credited attribution for a conversion.',
        'Validation': 'Checks for multiple CREDITED records linked to the same order.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'STALE_CART_TOTAL_AFTER_QUANTITY_UPDATE',
        'Purpose': 'Identifies cart totals that do not reconcile with the latest item quantities and prices.',
        'Validation': 'Recalculates cart-line totals and compares them with stored cart totals.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Order total accuracy',
        'Purpose': 'Checks whether order totals reconcile with their order lines.',
        'Validation': 'Compares stored order totals with the sum of line-item amounts.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Attribution revenue accuracy',
        'Purpose': 'Checks whether credited revenue agrees with the linked order and attribution rules.',
        'Validation': "Requires order-to-attribution links and the project's revenue-crediting rules.",        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Message event sequence',
        'Purpose': 'Identifies message events that occur before their corresponding send.',
        'Validation': 'Compares event timestamps with the associated send timestamp.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
    {
        'Rule': 'Campaign and template channel consistency',
        'Purpose': 'Identifies campaigns associated with templates using an incompatible channel.',
        'Validation': 'Compares campaign channels with their linked template channels.',
        'Status': 'NOT CHECKED',
        'Affected records': '—',
    },
]

checks_df = pd.DataFrame(checks)

total_checks = len(checks_df)
passed_checks = int((checks_df['Status'] == 'PASS').sum())
failed_checks = int((checks_df['Status'] == 'FAIL').sum())
unchecked_checks = int((checks_df['Status'] == 'NOT CHECKED').sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric('TOTAL RULES', total_checks)
k2.metric('PASSED', passed_checks)
k3.metric('FAILED', failed_checks)
k4.metric('NOT CHECKED', unchecked_checks)

st.markdown('### Validation results')

status_filter = st.selectbox(
    'Filter by status',
    ['All', 'PASS', 'FAIL', 'NOT CHECKED'],
    key='business_rules_status_filter'
)

if status_filter != 'All':
    displayed_df = checks_df[
        checks_df['Status'] == status_filter
    ]
else:
    displayed_df = checks_df

st.dataframe(
    displayed_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        'Rule': st.column_config.TextColumn('Business rule'),
        'Purpose': st.column_config.TextColumn('What it checks'),
        'Validation': st.column_config.TextColumn('Evidence required'),
        'Status': st.column_config.TextColumn('Status'),
        'Affected records': st.column_config.TextColumn(
            'Affected records'
        ),
    }
)

st.download_button(
    'Export validation report (CSV)',
    data=checks_df.to_csv(index=False).encode('utf-8-sig'),
    file_name='business_rules_validation_report.csv',
    mime='text/csv',
    key='business_rules_validation_export'
)

st.markdown('### How to interpret these results')

st.markdown(
    '''
    - **PASS:** The validation query ran successfully and found no violations.
    - **FAIL:** The validation query found one or more violations.
    - **NOT CHECKED:** The rule has not yet been validated against live data.
    '''
)

st.warning(
    'This page currently defines the validation report structure. '
    'The checks must be connected to their actual SQL validation queries '
    'before the dashboard can display real PASS/FAIL results or affected-record counts.'
)

st.caption(
    'Database safety: this section only displays report data and does '
    'not modify MySQL records.'
)
st.sidebar.divider(); 