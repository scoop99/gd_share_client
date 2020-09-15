# -*- coding: utf-8 -*-
#########################################################
# python
import os
from datetime import datetime
import traceback
import logging
import subprocess
import time
import re
import threading
import json
import platform
import requests

# third-party
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify

# sjva 공용
from framework import app, db, scheduler, path_app_root, socketio
from framework.job import Job
from framework.util import Util, AlchemyEncoder
from framework.common.share import RcloneTool
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name, SERVER_URL
from .logic import Logic
from .model import ModelSetting, ModelClientAVSubItem

#########################################################


class LogicAVSub(object):
    @staticmethod
    def process_ajax(sub, req):
        try:
            if sub == 'get_server_list':
                action = req.form['action']
                last_updated_time = ModelSetting.get('av_sub_last_updated_time')
                if action == 'all':
                    last_updated_time = ''
                def func():
                    ret = {'ret':False}
                    page = 1
                    count = 0
                    while True:
                        url = SERVER_URL + '/gd_share_server/noapi/av_sub/list?last_updated_time=%s&page=%s' % (last_updated_time, page)
                        logger.debug(url)
                        data = requests.get(url).json()
                        for item in data['list']:
                            #logger.debug(item)
                            ModelClientAVSubItem.insert(item)
                            count += 1
                        #if data['paging']['next_page'] == 0 or data['paging']['current_page'] == data['paging']['last_page']:
                        #logger.debug(data['paging'])
                        if data['paging']['current_page'] >= data['paging']['total_page']:
                            break
                        page += 1
                    ModelSetting.set('av_sub_last_updated_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S') )
                    ret['ret'] = True
                    ret['data'] = count
                    if action == 'all':
                        data = {'type':'info', 'msg' : u'%s개를 업데이트 했습니다.' % count, 'url':''}
                        socketio.emit("notify", data, namespace='/framework', broadcast=True)
                    return ret
                if action == 'all':
                    thread = threading.Thread(target=func, args=())
                    thread.setDaemon(True)
                    thread.start()
                    return jsonify(True)
                else:
                    ret = func()
                    return jsonify(ret)
            elif sub == 'get_server_count':
                url = SERVER_URL + '/gd_share_server/noapi/av_sub/count'
                data = requests.get(url).json()
                return jsonify(data) 
            elif sub == 'web_list':
                ret = ModelClientAVSubItem.web_list(req)
                return jsonify(ret)
            elif sub == 'get_by_folder_name':
                ret = ModelClientAVSubItem.get_by_folder_name(req.form['folder_name']).as_dict()
                return jsonify(ret)
            elif sub == 'plex_search':
                ret = LogicAVSub.plex_search(req.form['keyword'])
                return jsonify(ret)
            elif sub == 'srt_copy':
                ret = LogicAVSub.srt_copy(req.form['folder_name'], req.form['srt_index'])
                return jsonify(ret)
            elif sub == 'plex_refresh':
                ret = LogicAVSub.plex_refresh(req.form['metakey'], req.form['folder_name'])
                return jsonify(ret)     
            elif sub == 'do_action':
                logger.debug(req.form)
                mode = req.form['mode']
                server_type = req.form['server_type']
                folder_id = req.form['folder_id']
                folder_name = req.form['folder_name']
                server_filename = req.form['server_filename']
                remote_path = req.form['my_remote_path']
                action = req.form['action']
                mode = 'download' if mode == '0' else 'upload'
                server_type = 'category' if server_type == '0' else 'content'
                def func():
                    RcloneTool.do_action(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), mode, server_type, folder_id, folder_name, server_filename, remote_path, action, folder_id_encrypted=True)
                    if mode == 'upload' and server_type == 'content':
                        tmp = remote_path.split('/')
                        tmp2 = tmp[-1].split('.')
                        if tmp2[-1].lower() in ['mp4', 'mkv', 'avi', 'wmv', 'srt']:
                            url = SERVER_URL + '/gd_share_server/noapi/av_sub/refresh?folder_name=%s' % folder_name
                        else:
                            #url = SERVER_URL + '/gd_share_server/noapi/av_sub/refresh?folder_name=%s' % tmp[-1]
                            pass
                        data = requests.get(url).json()
                    msg = u'모두 완료되었습니다.\n'
                    socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                thread = threading.Thread(target=func, args=())
                thread.setDaemon(True)
                thread.start()
                return jsonify('')
            elif sub == 'plex_search_all':
                #return Response(LogicAVSub.plex_search_all(), mimetype="text/event-stream")
                LogicAVSub.plex_search_all()
                return jsonify('')
            elif sub == 'reset_db':
                db.session.query(ModelClientAVSubItem).delete()
                db.session.commit()
                ret = True
                return jsonify(ret)  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################

    @staticmethod
    def plex_search(keyword):
        try:
            logger.debug(keyword)
            from plex.logic_normal import LogicNormal
            data = LogicNormal.find_by_filename_part(keyword)

            item = ModelClientAVSubItem.get_by_folder_name(keyword)
            if len(data['list']) > 0:
                item.plex_metakey = ','.join(data['metadata_id'])
                item.remote_path = LogicAVSub.get_remote_path(data['list'][0]['dir'])
                data = LogicAVSub.set_remote_path(data)
            item.set_plex_json(data)
            logger.debug(data)
            return data
             
        except Exception as e: 
            logger.error('Exception:%s', e) 
            logger.error(traceback.format_exc())

    @staticmethod
    def plex_refresh(metakey, folder_name):
        try:
            from plex.logic_normal import LogicNormal
            data = LogicNormal.metadata_refresh(metadata_id=metakey.split('/')[-1])
            LogicAVSub.plex_search(folder_name)
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return False


    @staticmethod
    def get_remote_path(filepath):
        try:
            rule = ModelSetting.get('av_sub_plex_match_rule')
            if rule is not None:
                tmp = rule.split('|')
                ret = filepath.replace(tmp[1], tmp[0])
                if filepath[0] != '/':
                    ret = ret.replace('\\', '/')
                return ret.replace('//', '/').replace('\\\\', '\\')
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def set_remote_path(data):
        try:
            rule = ModelSetting.get('av_sub_plex_match_rule')
            tmp = rule.split('|')
            if rule == '':
                return data
            for item in data['list']:
                ret = item['filepath'].replace(tmp[1], tmp[0])
                if item['filepath'][0] != '/':
                    ret = ret.replace('\\', '/')
                ret = ret.replace('//', '/').replace('\\\\', '\\')
                item['remote_path'] = ret
            return data
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    

    @staticmethod
    def srt_copy(folder_name, source_index):
        try:
            item = ModelClientAVSubItem.get_by_folder_name(folder_name)
            logger.debug(item.plex_json)
             
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plex_search_all():
        try:
            def func():
                data = ModelClientAVSubItem.get_plex_search_all()
                log = u"%s개의 데이터를 분석을 시작합니다.\n" % len(data)
                socketio_callback('add', {'data':log})
                plex_log = log
                #data = data[:100]
                for index, tmp in enumerate(data):
                    ret = LogicAVSub.plex_search(tmp.folder_name)
                    log = u'%s / %s. %s => %s\n' % (index+1, len(data), tmp.folder_name, tmp.plex_metakey)
                    socketio_callback('add', {'data':log})
                    plex_log += log
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def get_path_list(key):
        tmps = ModelSetting.get_list(key)
        ret = []
        for t in tmps:
            if t.endswith('*'):
                dirname = os.path.dirname(t)
                listdirs = os.listdir(dirname)
                for l in listdirs:
                    ret.append(os.path.join(dirname, l))
            else:
                ret.append(t)
        return ret


    @staticmethod
    def get_download_remote_path(folder_name):
        tmps = LogicAVSub.get_path_list('av_sub_library_path')
        #logger.debug('folder_name: (%s)', folder_name)
        label = folder_name.split('-')[0].upper()
        path = os.path.join(ModelSetting.get('av_sub_no_library_path'), label)
        for t in tmps:
            tmp_path = os.path.join(t, label)
            if os.path.isdir(tmp_path):
                path = tmp_path
                break

        return LogicAVSub.get_remote_path(path)


#########################################################
# socketio / sub
#########################################################
sid_list = []
plex_log = ''
@socketio.on('connect', namespace='/%s/av_sub' % package_name)
def connect():
    try:
        logger.debug('socket_connect')
        sid_list.append(request.sid)
        socketio_callback('start', {'data':plex_log})
        #socketio_callback('connect',{})
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())


@socketio.on('disconnect', namespace='/%s/av_sub' % package_name)
def disconnect():
    try:
        sid_list.remove(request.sid)
        logger.debug('socket_disconnect')
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

def socketio_callback(cmd, data, encoding=True):
    if sid_list:
        if encoding:
            data = json.dumps(data, cls=AlchemyEncoder)
            data = json.loads(data)
        logger.debug(cmd)
        logger.debug(data)
        socketio.emit(cmd, data, namespace='/%s/av_sub' % package_name, broadcast=True)
        




class ModelClientAVSubItem(db.Model):
    __tablename__ = '%s_av_sub_item' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    updated_time = db.Column(db.DateTime)
    log = db.Column(db.String)
    creator = db.Column(db.String)

    # 구글
    folder_name = db.Column(db.String)
    folder_id_encrypted = db.Column(db.String)

    # 메타
    meta_json = db.Column(db.JSON)
    meta_type = db.Column(db.String)
    meta_code = db.Column(db.String)
    meta_title = db.Column(db.String)
    meta_poster = db.Column(db.String)
    meta_summury = db.Column(db.String)
    meta_actor = db.Column(db.String)
    meta_date = db.Column(db.String)

    # 파일목록
    video_count = db.Column(db.Integer)
    folder_size = db.Column(db.Integer)

    # 로컬
    is_exist = db.Column(db.Boolean)
    plex_metakey = db.Column(db.String)

    plex_json = db.Column(db.JSON)
    remote_path = db.Column(db.String)

    status = db.Column(db.Integer)

    def __init__(self, id):
        self.id = id
        self.is_exist = False
        self.plex_metakey = None


    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        ret['updated_time'] = self.updated_time.strftime('%m-%d %H:%M:%S') if self.updated_time is not None else None
        ret['files'] = [x.as_dict() for x in self.files]
        return ret

    def save(self):
        self.updated_time = datetime.now()
        db.session.add(self)
        db.session.commit()

    def set_plex_json(self, data):
        try:
            self.plex_json = data
            flag_modified(self, 'plex_json')
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_by_folder_name(folder_name):
        try:
            return db.session.query(ModelClientAVSubItem).filter_by(folder_name=folder_name).first()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_by_id(id):
        try:
            return db.session.query(ModelClientAVSubItem).filter_by(id=id).first()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def insert(server_json):
        try:
            data = ModelClientAVSubItem.get_by_id(server_json['id'])
            if data is None:
                data = ModelClientAVSubItem(server_json['id'])

            data.created_time = datetime.strptime(server_json['created_time'], '%Y-%m-%d %H:%M:%S')
            data.updated_time = datetime.strptime(server_json['updated_time'], '%Y-%m-%d %H:%M:%S')
            data.reserved = server_json['reserved']
            data.log = server_json['log']
            data.creator = server_json['creator']
            data.folder_name = server_json['folder_name']
            data.folder_id_encrypted = server_json['folder_id_encrypted']
            data.meta_json = server_json['meta_json']
            data.meta_type = server_json['meta_type']
            data.meta_code = server_json['meta_code']
            data.meta_title = server_json['meta_title']
            data.meta_poster = server_json['meta_poster']
            data.meta_summury = server_json['meta_summury']
            data.meta_actor = server_json['meta_actor']
            data.meta_date = server_json['meta_date']
            data.video_count = server_json['video_count']
            data.folder_size = server_json['folder_size']
            flag_modified(data, 'meta_json')
            for f in server_json['files']:
                ModelClientAVSubFile.insert(f, server_json['id'])
            data.status = server_json['status']
            db.session.add(data)
            db.session.commit()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def web_list(req):
        try:
            ret = {}
            page = 1
            page_size = 100
            job_id = ''
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            option_server = req.form['option_server'] if 'option_server' in req.form else 'all'
            option_client = req.form['option_client'] if 'option_client' in req.form else 'all'
            order = req.form['order'] if 'order' in req.form else 'name'

            query = ModelClientAVSubItem.make_query(search=search, option_server=option_server, option_client=option_client, order=order)
            last_list_option = '%s|%s|%s|%s|%s' % (search, option_server, option_client, order, page)
            ModelSetting.set('last_list_option', last_list_option)
            #logger.debug(query)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            logger.debug('ModelClientAVSubItem count:%s', count)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def make_query(search='', option_server='all', option_client='all', order='name'):
        query = db.session.query(ModelClientAVSubItem)
        conditions = []
        conditions.append(ModelClientAVSubItem.status == None)
        conditions.append(ModelClientAVSubItem.status != 1)
        query = query.filter(or_(*conditions))
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(ModelClientAVSubItem.folder_name.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(ModelClientAVSubItem.folder_name.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(ModelClientAVSubItem.folder_name.like('%'+search+'%'))

        if option_server != 'all':
            if option_server == 'server_only_srt':
                query = query.filter(ModelClientAVSubItem.video_count == 0)
            elif option_server == 'server_include_video':
                query = query.filter(ModelClientAVSubItem.video_count > 0)
        
        if option_client != 'all':
            if option_client == 'client_plex_no_meta':
                query = query.filter(ModelClientAVSubItem.plex_metakey == None)
            elif option_client == 'client_plex_exist_meta':
                query = query.filter(ModelClientAVSubItem.plex_metakey != None)

        if order == 'name':
            query = query.order_by(ModelClientAVSubItem.folder_name)
        elif order == 'name_desc':
            query = query.order_by(desc(ModelClientAVSubItem.folder_name))
        elif order == 'date':
            query = query.order_by(ModelClientAVSubItem.meta_date)
        elif order == 'date_desc':
            query = query.order_by(desc(ModelClientAVSubItem.meta_date))
        elif order == 'update':
            query = query.order_by(ModelClientAVSubItem.updated_time)
        elif order == 'update_desc':
            query = query.order_by(desc(ModelClientAVSubItem.updated_time))
        elif order == 'index':
            query = query.order_by(ModelClientAVSubItem.id)
        elif order == 'index_desc':
            query = query.order_by(desc(ModelClientAVSubItem.id))

        return query  

    @staticmethod
    def get_plex_search_all():
        query = ModelClientAVSubItem.make_query(option_client='client_plex_no_meta', order='update_desc')
        return query.all()




class ModelClientAVSubFile(db.Model):
    __tablename__ = '%s_av_sub_file' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    uploader = db.Column(db.String)
    # ffprobe
    filename = db.Column(db.String)
    filesize = db.Column(db.Integer)
    duration = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    ffprobe_json = db.Column(db.JSON)

    # 2
    bitrate = db.Column(db.Integer)
    codec_name = db.Column(db.String)

    item_id = db.Column(db.Integer, db.ForeignKey('%s_av_sub_item.id' % package_name))
    item = db.relationship('ModelClientAVSubItem', backref='files', lazy=True)

    def __init__(self, id, item_id):
        self.id = id
        self.item_id = item_id

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        return ret
    
    def save(self):
        db.session.add(self)
        db.session.commit()
    
    @staticmethod
    def get_by_filename(filename):
        try:
            return db.session.query(ModelClientAVSubFile).filter_by(filename=filename).first()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_by_id(id):
        try:
            return db.session.query(ModelClientAVSubFile).filter_by(id=id).first()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def insert(server_json, item_id):
        try:
            data = ModelClientAVSubFile.get_by_id(server_json['id'])
            if data is None:
                data = ModelClientAVSubFile(server_json['id'], item_id)

            data.created_time = datetime.strptime(server_json['created_time'], '%Y-%m-%d %H:%M:%S')
            data.reserved = server_json['reserved']
            data.uploader = server_json['uploader']
            data.filename = server_json['filename']
            data.filesize = server_json['filesize']
            data.duration = server_json['duration']
            data.width = server_json['width']
            data.height = server_json['height']
            data.ffprobe_json = server_json['ffprobe_json']
            data.bitrate = server_json['bitrate']
            data.codec_name = server_json['codec_name']
            
            flag_modified(data, 'ffprobe_json')
            #logger.debug(json.dumps(server_json, indent=2))
            
            db.session.add(data)
            db.session.commit()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            