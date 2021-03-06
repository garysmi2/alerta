import datetime

from flask import g, request, render_template
from flask.ext.cors import cross_origin
#from uuid import uuid4

from alerta.app import app, db
from alerta.app.switch import Switch
from alerta.app.auth import auth_required, admin_required
from alerta.app.utils import jsonify, jsonp, parse_fields, process_alert, getTenantFromHeader, generateDBName, getSitewhereTenantInfo, getDeviceInfo
from alerta.app.metrics import Timer
from alerta.alert import Alert
from alerta.heartbeat import Heartbeat
from alerta.plugins import RejectException
from flask import request

LOG = app.logger

# Set-up metrics
gets_timer = Timer('alerts', 'queries', 'Alert queries', 'Total time to process number of alert queries')
receive_timer = Timer('alerts', 'received', 'Received alerts', 'Total time to process number of received alerts')
delete_timer = Timer('alerts', 'deleted', 'Deleted alerts', 'Total time to process number of deleted alerts')
status_timer = Timer('alerts', 'status', 'Alert status change', 'Total time and number of alerts with status changed')
tag_timer = Timer('alerts', 'tagged', 'Tagging alerts', 'Total time to tag number of alerts')
untag_timer = Timer('alerts', 'untagged', 'Removing tags from alerts', 'Total time to un-tag number of alerts')


'''
@app.route('/_', methods=['OPTIONS', 'PUT', 'POST', 'DELETE', 'GET'])
@cross_origin()
@jsonp
def test():

    return jsonify(
        status="ok",
        method=request.method,
        json=request.json,
        data=request.data.decode('utf-8'),
        args=request.args,
        app_root=app.root_path,
    )
'''

'''
@app.route('/')
def index():

    rules = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint not in ['test', 'static']:
            rules.append(rule)
    return render_template('index.html', rules=rules)
'''

@app.route("/alerts/", methods=['GET'])
@cross_origin()
@auth_required
def get_alerts():

    tenant = getTenantFromHeader(request)

    if len(tenant) == 0:
        return jsonify(status="error", message="bad request"), 400

    tenant = generateDBName(tenant)
    gets_started = gets_timer.start_timer()

    try:
        query, sort, _, page, limit, query_time = parse_fields(request)
    except Exception as e:
        gets_timer.stop_timer(gets_started)
        return jsonify(status="error", message=str(e)), 400

    try:
        severity_count = db.get_counts(tenant, query=query, fields={"severity": 1}, group="severity")
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    try:
        status_count = db.get_counts(tenant, query=query, fields={"status": 1}, group="status")
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if limit < 1:
        return jsonify(status="error", message="page 'limit' of %s is not valid" % limit), 416

    total = sum(severity_count.values())
    pages = ((total - 1) // limit) + 1

    if total and page > pages or page < 0:
        return jsonify(status="error", message="page out of range: 1-%s" % pages), 416

    fields = dict()
    fields['history'] = {'$slice': app.config['HISTORY_LIMIT']}

    try:
        alerts = db.get_alerts(tenant, query=query, fields=fields, sort=sort, page=page, limit=limit)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    alert_response = list()
    if len(alerts) > 0:

        last_time = None

        for alert in alerts:
            body = alert.get_body()
            body['href'] = "%s/%s" % (request.base_url.replace('alerts', 'alert'), alert.id)

            if not last_time:
                last_time = body['lastReceiveTime']
            elif body['lastReceiveTime'] > last_time:
                last_time = body['lastReceiveTime']

            alert_response.append(body)

        gets_timer.stop_timer(gets_started)
        return jsonify(
            status="ok",
            total=total,
            page=page,
            pageSize=limit,
            pages=pages,
            more=page < pages,
            alerts=alert_response,
            severityCounts=severity_count,
            statusCounts=status_count,
            lastTime=last_time,
            autoRefresh=Switch.get('auto-refresh-allow').is_on(),
        )
    else:
        gets_timer.stop_timer(gets_started)
        return jsonify(
            status="ok",
            message="not found",
            total=total,
            page=page,
            pageSize=limit,
            pages=pages,
            more=False,
            alerts=[],
            severityCounts=severity_count,
            statusCounts=status_count,
            lastTime=query_time,
            autoRefresh=Switch.get('auto-refresh-allow').is_on()
        )


@app.route('/alerts/<tenant>/history', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_history(tenant):

    tenant = generateDBName(tenant)

    try:
        query, _, _, _, limit, query_time = parse_fields(request)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    try:
        history = db.get_history(tenant, query=query, limit=limit)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    for alert in history:
        alert['href'] = "%s/%s" % (request.base_url.replace('alerts/history', 'alert'), alert['id'])

    if len(history) > 0:
        return jsonify(
            status="ok",
            history=history,
            lastTime=history[-1]['updateTime']
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            history=[],
            lastTIme=query_time
        )


@app.route('/alert/<tenant>', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@jsonp
def receive_alert(tenant):

##    recv_started = receive_timer.start_timer()

    tenant = generateDBName(tenant)

    try:
        incomingAlert = Alert.parse_alert(request.data)
    except ValueError as e:
##        receive_timer.stop_timer(recv_started)
        return jsonify(status="error", message=str(e)), 400

    if g.get('customer', None):
        incomingAlert.customer = g.get('customer')

    if request.headers.getlist("X-Forwarded-For"):
       incomingAlert.attributes.update(ip=request.headers.getlist("X-Forwarded-For")[0])
    else:
       incomingAlert.attributes.update(ip=request.remote_addr)

    try:
        alert = process_alert(incomingAlert, tenant)
    except RejectException as e:
#        receive_timer.stop_timer(recv_started)
        return jsonify(status="error", message=str(e)), 403
    except RuntimeWarning as e:
#        receive_timer.stop_timer(recv_started)
        return jsonify(status="ok", id=incomingAlert.id, message=str(e)), 202
    except Exception as e:
#        receive_timer.stop_timer(recv_started)
        return jsonify(status="error", message=str(e)), 500

#    receive_timer.stop_timer(recv_started)

    if alert:
        body = alert.get_body()
        body['href'] = "%s/%s" % (request.base_url, alert.id)
        return jsonify(status="ok", id=alert.id, alert=body), 201, {'Location': '%s/%s' % (request.base_url, alert.id)}
    else:
        return jsonify(status="error", message="insert or update of received alert failed"), 500


@app.route('/alert/<tenant>/<id>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_alert(tenant,id):

    tenant = generateDBName(tenant)

    try:
        alert = db.get_alert(tenant, id=id)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if alert:
        if g.get('role', None) != 'admin' and not alert.customer == g.get('customer', None):
            return jsonify(status="error", message="not found", total=0, alert=None), 404
        body = alert.get_body()
        body['href'] = request.base_url
        return jsonify(status="ok", total=1, alert=body)
    else:
        return jsonify(status="error", message="not found", total=0, alert=None), 404


@app.route('/alert/<id>/status', methods=['POST'])
@cross_origin()
def set_status(id):

    # FIXME - should only allow role=user to set status for alerts for that customer
    # Above comment is from original code, can ignore it for now


    status_started = status_timer.start_timer()

    tenant = getTenantFromHeader(request)

    if len(tenant) == 0:
        return jsonify(status="error", message="bad request"), 400

    data = request.json

    tenant = generateDBName(tenant)

    if data and 'status' in data:
        try:
            alert = db.set_status(tenant, id=id, status=data['status'], text=data.get('text', ''))
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500
    else:
        status_timer.stop_timer(status_started)
        return jsonify(status="error", message="must supply 'status' as parameter"), 400

    if alert:
        status_timer.stop_timer(status_started)
        return jsonify(status="ok")
    else:
        status_timer.stop_timer(status_started)
        return jsonify(status="error", message="not found"), 404


@app.route('/alert/<tenant>/<id>/tag', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@jsonp
def tag_alert(tenant, id):

    # FIXME - should only allow role=user to set status for alerts for that customer
    # Above comment is from original code, can ignore for now

    tag_started = tag_timer.start_timer()

    data = request.json

    tenant = generateDBName(tenant)

    if data and 'tags' in data:
        try:
            response = db.tag_alert(id, tenant, data['tags'])
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500
    else:
        tag_timer.stop_timer(tag_started)
        return jsonify(status="error", message="must supply 'tags' as list parameter"), 400

    tag_timer.stop_timer(tag_started)
    if response:
        return jsonify(status="ok")
    else:
        return jsonify(status="error", message="not found"), 404


@app.route('/alert/<tenant>/<id>/untag', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@jsonp
def untag_alert(tenant, id):

    # FIXME - should only allow role=user to set status for alerts for that customer
    # Above comment is from original code, can ignore for now

    untag_started = untag_timer.start_timer()
    data = request.json

    tenant = generateDBName(tenant)

    if data and 'tags' in data:
        try:
            response = db.untag_alert(id, tenant, data['tags'])
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500
    else:
        untag_timer.stop_timer(untag_started)
        return jsonify(status="error", message="must supply 'tags' as list parameter"), 400

    untag_timer.stop_timer(untag_started)
    if response:
        return jsonify(status="ok")
    else:
        return jsonify(status="error", message="not found"), 404


@app.route('/alert/<tenant>/<id>', methods=['OPTIONS', 'DELETE'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_alert(tenant,id):

    started = delete_timer.start_timer()

    tenant = generateDBName(tenant)

    try:
        response = db.delete_alert(tenant,id)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500
    delete_timer.stop_timer(started)

    if response:
        return jsonify(status="ok")
    else:
        return jsonify(status="error", message="not found"), 404


# Return severity and status counts
@app.route('/alerts/<tenant>/count', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_counts(tenant):

    tenant = generateDBName(tenant)

    try:
        query, _, _, _, _, _ = parse_fields(request)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    try:
        severity_count = db.get_counts(tenant, query=query, fields={"severity": 1}, group="severity")
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    try:
        status_count = db.get_counts(tenant, query=query, fields={"status": 1}, group="status")
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if sum(severity_count.values()):
        return jsonify(
            status="ok",
            total=sum(severity_count.values()),
            severityCounts=severity_count,
            statusCounts=status_count
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            severityCounts=severity_count,
            statusCounts=status_count
        )


@app.route('/alerts/<tenant>/top10', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_top10(tenant):

    tenant = generateDBName(tenant)

    try:
        query, _, group, _, _, _ = parse_fields(request)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    try:
        top10 = db.get_topn(tenant, query=query, group=group, limit=10)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    for item in top10:
        for resource in item['resources']:
            resource['href'] = "%s/%s" % (request.base_url.replace('alerts/top10', 'alert'), resource['id'])

    if top10:
        return jsonify(
            status="ok",
            total=len(top10),
            top10=top10
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            top10=[],
        )


@app.route('/environments/<tenant>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_environments(tenant):

    tenant = generateDBName(tenant)

    try:
        query, _, _, _, limit, _ = parse_fields(request)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    try:
        environments = db.get_environments(tenant, query=query, limit=limit)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if environments:
        return jsonify(
            status="ok",
            total=len(environments),
            environments=environments
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            environments=[],
        )


@app.route('/services/<tenant>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_services(tenant):

    tenant = generateDBName(tenant)

    try:
        query, _, _, _, limit, _ = parse_fields(request)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    try:
        services = db.get_services(tenant, query=query, limit=limit)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if services:
        return jsonify(
            status="ok",
            total=len(services),
            services=services
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            services=[],
        )


@app.route('/blackouts/<tenant>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def get_blackouts(tenant):

    tenant = generateDBName(tenant)

    try:
        blackouts = db.get_blackouts(tenant)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if len(blackouts):
        return jsonify(
            status="ok",
            total=len(blackouts),
            blackouts=blackouts,
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            blackouts=[],
            time=datetime.datetime.utcnow()
        )


@app.route('/blackout/<tenant>', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def create_blackout(tenant):

    data = request.json

    tenant = generateDBName(tenant)

    if request.json and 'environment' in request.json:
        environment = request.json['environment']
    else:
        return jsonify(status="error", message="must supply 'environment' as parameter"), 400

    resource = request.json.get("resource", None)
    service = request.json.get("service", None)
    event = request.json.get("event", None)
    group = request.json.get("group", None)
    tags = request.json.get("tags", None)
    start_time = request.json.get("startTime", None)
    end_time = request.json.get("endTime", None)
    duration = request.json.get("duration", None)

    if start_time:
        start_time = datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    if end_time:
        end_time = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')

    try:
        blackout = db.create_blackout(tenant,environment, resource, service, event, group, tags, start_time, end_time, duration)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    return jsonify(status="ok", blackout=blackout), 201, {'Location': '%s/%s' % (request.base_url, blackout)}


@app.route('/blackout/<tenant>/<path:blackout>', methods=['OPTIONS', 'DELETE'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_blackout(tenant, blackout):

    tenant = generateDBName(tenant)

    try:
        response = db.delete_blackout(tenant, blackout)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if response:
        return jsonify(status="ok")
    else:
        return jsonify(status="error", message="not found"), 404


@app.route('/heartbeats/<tenant>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_heartbeats(tenant):

    tenant = generateDBName(tenant)

    try:
        heartbeats = db.get_heartbeats(tenant)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    hb_list = list()
    for hb in heartbeats:
        body = hb.get_body()
        if g.get('role', None) != 'admin' and not body['customer'] == g.get('customer', None):
            continue
        body['href'] = "%s/%s" % (request.base_url.replace('heartbeats', 'heartbeat'), hb.id)
        hb_list.append(body)

    if hb_list:
        return jsonify(
            status="ok",
            total=len(heartbeats),
            heartbeats=hb_list,
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            heartbeats=hb_list,
            time=datetime.datetime.utcnow()
        )


@app.route('/heartbeat/<tenant>', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@jsonp
def create_heartbeat(tenant):

    tenant = generateDBName(tenant)

    try:
        heartbeat = Heartbeat.parse_heartbeat(request.data)
    except ValueError as e:
        return jsonify(status="error", message=str(e)), 400


    if g.get('role', None) != 'admin':
        heartbeat.customer = g.get('customer', None)


    try:
        heartbeat = db.save_heartbeat(tenant, heartbeat)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    body = heartbeat.get_body()
    body['href'] = "%s/%s" % (request.base_url, heartbeat.id)
    return jsonify(status="ok", id=heartbeat.id, heartbeat=body), 201, {'Location': '%s/%s' % (request.base_url, heartbeat.id)}


@app.route('/heartbeat/<tenant>/<id>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_heartbeat(tenant,id):

    tenant = generateDBName(tenant)

    try:
        heartbeat = db.get_heartbeat(tenant, id=id)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if heartbeat:
        if g.get('role', None) != 'admin' and not heartbeat.customer == g.get('customer', None):
            return jsonify(status="error", message="not found", total=0, alert=None), 404
        body = heartbeat.get_body()
        body['href'] = request.base_url
        return jsonify(status="ok", total=1, heartbeat=body)
    else:
        return jsonify(status="error", message="not found", total=0, heartbeat=None), 404


@app.route('/heartbeat/<tenant>/<id>', methods=['OPTIONS', 'DELETE'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_heartbeat(tenant, id):

    tenant =  generateDBName(tenant)

    try:
        response = db.delete_heartbeat(tenant, id)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if response:
        return jsonify(status="ok")
    else:
        return jsonify(status="error", message="not found"), 404


@app.route('/device/<deviceid>', methods=['GET'])
@cross_origin()
def get_device(deviceid):
    tenant = getTenantFromHeader(request)

    if len(tenant) == 0:
        return jsonify(status="error", message="bad request"), 400

    response = getSitewhereTenantInfo(tenant)


    if response and response.status_code is not 200:
        return jsonify(status=response.reason, message=response.content), response.status_code

    response = response.json()

    try:

        authToken = response['authenticationToken']

        url = "http://scamps.cit.ie:8888/sitewhere/api/devices/" + deviceid

        response = getDeviceInfo(url, authToken)

        print response
        print response.text
        print response.request.headers
        return jsonify(message=response.text), response.status_code
    except KeyError as ke:

        return jsonify(status="401",message="authentication token missing"), 401




'''
@app.route('/users', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def get_users():

    try:
        users = db.get_users()
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if len(users):
        return jsonify(
            status="ok",
            total=len(users),
            users=users,
            domains=app.config['ALLOWED_EMAIL_DOMAINS'],
            orgs=app.config['ALLOWED_GITHUB_ORGS'],
            groups=app.config['ALLOWED_GITLAB_GROUPS'],
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            users=[],
            domains=app.config['ALLOWED_EMAIL_DOMAINS'],
            orgs=app.config['ALLOWED_GITHUB_ORGS'],
            time=datetime.datetime.utcnow()
        )


@app.route('/user', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def create_user():

    if request.json and 'name' in request.json:
        name = request.json["name"]
        login = request.json["login"]
        password = request.json.get("password", None)
        provider = request.json["provider"]
        text = request.json.get("text", "")
        try:
            user = db.save_user(str(uuid4()), name, login, password, provider, text)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500
    else:
        return jsonify(status="error", message="must supply user 'name', 'login' and 'provider' as parameters"), 400

    if user:
        return jsonify(status="ok", user=user), 201, {'Location': '%s/%s' % (request.base_url, user)}
    else:
        return jsonify(status="error", message="User with that login already exists"), 409


@app.route('/user/<user>', methods=['OPTIONS', 'PUT'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def update_user(user):

    if 'password' in request.json:
        try:
            password = request.json["password"]
            response = db.reset_user_password(user, password)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500

        if response:
            return jsonify(status="ok")
        else:
            return jsonify(status="error", message="not found"), 404

    else:
        return jsonify(status="error", message="Must supply new password for user")


@app.route('/user/<user>', methods=['OPTIONS', 'DELETE', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_user(user):

    if request.method == 'DELETE' or (request.method == 'POST' and request.json['_method'] == 'delete'):
        try:
            response = db.delete_user(user)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500

        if response:
            return jsonify(status="ok")
        else:
            return jsonify(status="error", message="not found"), 404


@app.route('/customers', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def get_customers():

    try:
        customers = db.get_customers()
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if len(customers):
        return jsonify(
            status="ok",
            total=len(customers),
            customers=customers,
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            customers=[],
            time=datetime.datetime.utcnow()
        )


@app.route('/customer', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def create_customer():

    if request.json and 'customer' in request.json and 'match' in request.json:
        customer = request.json["customer"]
        match = request.json["match"]
        try:
            cid = db.create_customer(customer, match)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500
    else:
        return jsonify(status="error", message="must supply user 'customer' and 'match' as parameters"), 400

    if cid:
        return jsonify(status="ok", id=cid), 201, {'Location': '%s/%s' % (request.base_url, cid)}
    else:
        return jsonify(status="error", message="Customer lookup for this match already exists"), 409


@app.route('/customer/<customer>', methods=['OPTIONS', 'DELETE', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_customer(customer):

    if request.method == 'DELETE' or (request.method == 'POST' and request.json['_method'] == 'delete'):
        try:
            response = db.delete_customer(customer)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500

        if response:
            return jsonify(status="ok")
        else:
            return jsonify(status="error", message="not found"), 404


@app.route('/keys', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_keys():

    query = dict()
    if g.get('role', None) != 'admin':
        query['customer'] = g.get('customer')

    try:
        keys = db.get_keys(query)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if len(keys):
        return jsonify(
            status="ok",
            total=len(keys),
            keys=keys,
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            keys=[],
            time=datetime.datetime.utcnow()
        )


@app.route('/keys/<user>', methods=['OPTIONS', 'GET'])
@cross_origin()
@auth_required
@jsonp
def get_user_keys(user):

    query = {"user": user}
    if g.get('role', None) != 'admin':
        query['customer'] = g.get('customer')

    try:
        keys = db.get_keys(query)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    if len(keys):
        return jsonify(
            status="ok",
            total=len(keys),
            keys=keys,
            time=datetime.datetime.utcnow()
        )
    else:
        return jsonify(
            status="ok",
            message="not found",
            total=0,
            keys=[],
            time=datetime.datetime.utcnow()
        )


@app.route('/key', methods=['OPTIONS', 'POST'])
@cross_origin()
@auth_required
@jsonp
def create_key():

    if request.json and 'user' in request.json:
        user = request.json['user']
    else:
        return jsonify(status="error", message="must supply 'user' as parameter"), 400

    type = request.json.get("type", "read-only")
    if type not in ['read-only', 'read-write']:
        return jsonify(status="error", message="API key must be read-only or read-write"), 400

    customer = g.get('customer', None) or request.json.get("customer", None)
    text = request.json.get("text", "API Key for %s" % user)
    try:
        key = db.create_key(user, type, customer, text)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    return jsonify(status="ok", key=key), 201, {'Location': '%s/%s' % (request.base_url, key)}


@app.route('/key/<path:key>', methods=['OPTIONS', 'DELETE', 'POST'])
@cross_origin()
@auth_required
@admin_required
@jsonp
def delete_key(key):

    query = {"key": key}
    if not db.get_keys(query):
        return jsonify(status="error", message="not found"), 404

    if request.method == 'DELETE' or (request.method == 'POST' and request.json['_method'] == 'delete'):
        try:
            response = db.delete_key(key)
        except Exception as e:
            return jsonify(status="error", message=str(e)), 500

        if response:
            return jsonify(status="ok")
        else:
            return jsonify(status="error", message="not found"), 404
'''
