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
        
