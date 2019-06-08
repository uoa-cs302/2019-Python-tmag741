import time
import centralAPI
import clientAPI
import message_handler
import session_handler
import helper
import json
import threading
import cherrypy

LOCATION_ADRESS = "http://302cherrypy.mynetgear.com/"
WORLD_CONNECTION = '2'
SESSION_DB = 'session.db'

@cherrypy.config(**{'tools.cors.on': True})
class Interface(object):
  
    @cherrypy.expose
    def default(self, *args, **kwargs):
        return Interface.index(self)

    @cherrypy.expose
    def index(self):
        response = {'response':'error', 'message':'Invalid access point'}
        response_JSON = json.dumps(response)
        return response_JSON
    # typeCheck 0 for just login/unlock_data/add_pubkey/check_privatedata 1 for everything else
    def isLoggedIn(self,user,typeCheck): 
        if(typeCheck == 1):
            if(session_handler.userCheck(user)):
                APIKey = session_handler.userAPIKey(user)
                privateKey = session_handler.userKeys(user)[0][0]
                centralResponse = centralAPI.ping(APIKey,user,privateKey)
                if(centralResponse == "error" or centralResponse['response'] == "error"):
                    return False
            return True
        elif(typeCheck == 0):
            if(session_handler.userCheck(user) == False):
                return False
            return True
            

    # Using header to get IP, i can block their requests to this end point
    # One of the reasons is to minimise frontend pinging hammond/central server
    @cherrypy.expose
    def user_list(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))

        if (self.isLoggedIn(self, body_json['username'], 1) == False):
            return '2'

        centralResponse = centralAPI.list_users(self.apikey, self.username)
        if (centralResponse['response'] == 'ok'):
            newList = []
            userList = centralResponse['users']
            self.checkList = centralResponse['users']
            for user in userList:
                if (user['username'] != self.username):
                    newList.append(user['username'])

            jsonToSend = {}
            jsonToSend['amount'] = len(newList)
            jsonToSend['userList'] = newList
            responseBody = json.dumps(jsonToSend)
            return (responseBody)
        else:
            return '0'

    @cherrypy.expose
    def login(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        centralResponse = centralAPI.load_new_apikey(body_json['user'], body_json['pass'])
        if(centralResponse == 'error'):
            return '0'

        if (centralResponse['response'] == "ok"):
            session_handler.addUser(body_json['user'], centralResponse['api_key'])
            return '1'

    @cherrypy.expose
    def check_privatedata(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']

        if (self.isLoggedIn(username,0) == False):
            return '2'

        APIKey = session_handler.userAPIKey(username)
        
        centralResponse = centralAPI.get_privatedata(APIKey, username)
        if(centralResponse == "error"):
            return '0'

        if (centralResponse['response'] == "ok"):
            session_handler.updatePrivateData(username, centralResponse['privatedata'])
            return '1'
        else:
            return '0'


    # Need to check if they're logged in
    @cherrypy.expose
    def unlock_privatedata(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        decryptKey = body_json['decryptionKey']
        
        if (self.isLoggedIn(username, 0) == False):
            return '2'

        lockedData = session_handler.userPrivateData(username)
        unlockedData = helper.decryptData(lockedData, decryptKey)

        if (unlockedData != "error"):
            privateKeyData = unlockedData['prikeys']
            privateKey = privateKeyData[0]
            publicKey = helper.generatePubKey(privateKey)
            EDKey = decryptKey

            session_handler.updatePrivateData(username, str(unlockedData))
            session_handler.updateKeys(username,privateKey,publicKey)
            session_handler.updateEDKey(username,EDKey)
            return '1'
        else:
            return '0'

    @cherrypy.expose
    def logout(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        if (self.isLoggedIn(username, 0) == False):
            return '2'
        # add to database
        if (self.newData == True):
            userdata_ecrypted = helper.encryptData(self.privateData, self.EDKey)
            centralResponse = centralAPI.add_privatedata(self.apikey, self.username, userdata_ecrypted, self.privateKey)
            if (centralResponse['response'] == "error"):
                return '0'
        # delete session
        centralResponse = centralAPI.report(self.apikey, self.username, "LOCATION N/A", "2", self.publicKey, "offline")

        return '1'

    @cherrypy.expose
    def get_publicMessages(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        if (self.isLoggedIn(username, 0) == False):
            return '2'        
        
        message_list = message_handler.fetchPublicMessages()
        return json.dumps(message_list)

      

    @cherrypy.expose
    def broadcast(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        if (self.isLoggedIn(username, 1) == False):
            return '2'

        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        message = body_json['message']
        epoch = time.time()
        epoch_str = str(epoch)
        message_handler.updatePublicMessages(username, message, epoch)
        
        APIkey = session_handler.userAPIKey(username)
        private_key = session_handler.userKeys(username)[0][0]

        centralResponse = centralAPI.rx_broadcast(APIkey,username, message, epoch_str, private_key)
        return '1'


    @cherrypy.expose
    def add_pubkey(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        if (self.isLoggedIn(username, 0) == False):
            return '2'

        self.newData = True
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        APIkey = session_handler.userAPIKey(username)
        private_key = session_handler.userKeys(username)[0][0]
        centralResponse = centralAPI.add_pubkey(APIkey,private_key)
        if (centralResponse == "error"):
            return '0'
        else:
            self.EDKey = body_json['encryptionKey']
            self.privateKey = centralResponse['private_key']
            self.publicKey = centralResponse['public_key']
            return '1'

    @cherrypy.expose
    def updateStatus(self):
        FUCK = 'SAKE'

    @cherrypy.expose
    def intervalCheck(self):
        # Update list -> via my cred
        # ping
        if(self.checkList == None):
            centralResponse = centralAPI.list_users(self.apikey, self.username)
            if (centralResponse['response'] == 'ok'):
                newList = []
                userList = centralResponse['users']
                self.checkList = centralResponse['users']

        pingThread = threading.Thread(target=helper.pingThread, args=(self.checkList, LOCATION_ADRESS, WORLD_CONNECTION))
        try:
            pingThread.start()
        except Exception as error:
            pass

        return '1';

    @cherrypy.expose
    def report_user(self):
        body = cherrypy.request.body.read()
        body_json = json.loads(body.decode('utf-8'))
        username = body_json['username']
        userStatus = body_json['userStatus']
        
        if (self.isLoggedIn(username, 1) == False):
            return '2'
        
        print("===================")
        print(session_handler.userKeys(username)[0][1])
        print("===================")

        APIkey = session_handler.userAPIKey(username)
        public_key = session_handler.userKeys(username)[0][1]
        centralResponse = centralAPI.report(APIkey, username, LOCATION_ADRESS, WORLD_CONNECTION, public_key, userStatus)
        
        if (centralResponse['response'] == 'ok'):
            return '1'
        else:
            return '0'
