import os
import json
import zipfile
import adal
import flask
import uuid
import requests
import config
import datetime

app = flask.Flask(__name__)
app.debug = True
app.secret_key = 'development'

PORT = 5000
AUTHORITY_URL = config.AUTHORITY_HOST_URL + '/' + config.TENANT
REDIRECT_URI = 'http://localhost:{}/getAToken'.format(PORT)
TEMPLATE_AUTHZ_URL = ('https://login.microsoftonline.com/{}/oauth2/authorize?' +
                      'response_type=code&client_id={}&redirect_uri={}&' +
                      'state={}&resource={}')


@app.route("/")
def main():
    login_url = 'http://localhost:{}/login'.format(PORT)
    resp = flask.Response(status=307)
    resp.headers['location'] = login_url
    return resp


@app.route("/login")
def login():
    auth_state = str(uuid.uuid4())
    flask.session['state'] = auth_state
    authorization_url = TEMPLATE_AUTHZ_URL.format(
        config.TENANT,
        config.CLIENT_ID,
        REDIRECT_URI,
        auth_state,
        config.RESOURCE)
    resp = flask.Response(status=307)
    resp.headers['location'] = authorization_url
    return resp


@app.route("/getAToken")
def main_logic():
    code = flask.request.args['code']
    state = flask.request.args['state']
    if state != flask.session['state']:
        raise ValueError("State does not match")
    auth_context = adal.AuthenticationContext(AUTHORITY_URL)
    token_response = auth_context.acquire_token_with_authorization_code(code, REDIRECT_URI, config.RESOURCE,
                                                                        config.CLIENT_ID, config.CLIENT_SECRET)
    # It is recommended to save this to a database when using a production app.
    flask.session['access_token'] = token_response['accessToken']

    return flask.redirect('/graphcall')


@app.route('/graphcall')
def graphcall():
    if 'access_token' not in flask.session:
        return flask.redirect(flask.url_for('login'))
    http_headers = {'Authorization': 'Bearer ' + flask.session.get('access_token'),
                    'User-Agent': 'adal-python-sample',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'client-request-id': str(uuid.uuid4())}
    url_users = 'https://graph.microsoft.com/v1.0/users'
    url_groups = 'https://graph.microsoft.com/v1.0/groups'
    graph_data_users = requests.get(url_users, headers=http_headers).json()
    graph_data_groups = requests.get(url_groups, headers=http_headers).json()

    path = str(datetime.datetime.now().strftime('%Y_%m_%d__%H_%M_%S'))
    if path not in os.listdir(os.getcwd()):
        try:
            os.mkdir(path)
        except OSError as e:
            print(e)

    path_zip = os.getcwd() + '\\' + path + '\\' + path + '_json.zip'
    with zipfile.ZipFile(path_zip, 'w') as newfilezip:
        newfilezip.writestr(path + '_users.json', json.dumps(graph_data_users))
        newfilezip.writestr(path + '_groups.json', json.dumps(graph_data_groups))

    if 'error' in dict(graph_data_users).keys():
        return flask.render_template_string('<div>{}</div>'.format(str(graph_data_users)))
    else:
        return flask.render_template('display_graph_info.html', graph_data=dict(graph_data_users))


if __name__ == "__main__":
    app.run()
