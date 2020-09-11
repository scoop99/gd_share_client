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
from framework.util import Util
from framework.common.share import RcloneTool
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name, SERVER_URL
from .logic import Logic
from .model import ModelSetting

#########################################################


category_list = [
    { 'type' : 'share_movie', 'name' : u'영화', 'list' : [
        [u'국내', '+3GSRdSQqijI/FUenjzYeuLwvpTQSWsP21UbPT1LCi7yxz3n3M6KpmkfIAkU4W3uRZFMwMET0R5J2kkpq8mk6Q=='], 
        [u'외국', 't7KWVIHwgW/96Pjd/poo+tVmAgMyIt/Cga83rOLQqK5T0jh/OGKzt9Csvbfr4vfcPvoJ8o8cd8AaEHC5iLtx1Q=='],
        [u'최신', 'MBoXLEq8fKHgb+XaQk52I+Q032HSO9LGCcSw7HBtB4CME2uXSlS4hd/uZpEWjuzN/9GWaZLFhSjQsxvdTmAVHw=='],
        [u'더빙', 'tSPKo3br/eemuusJfChrcu4iiizRPjTWqZ00XjwxzvXGJWsIYZNhm/NIumYQUrabrmyVnL+eywwqBSFQbK4QlA=='],
    ]},
    { 'type' : 'share_ktv', 'name' : u'국내TV(종영)', 'list' : [
        [u'드라마', 'dwlfA65x2nuOamUMGWiWtAhsPrZAlZSeJn4EtJv7X9xhnSOtrNT3Z9yndlej2bYDgB+8IlDRH5/mmmqCBLu2Mw=='], 
        [u'예능', 'qDWsbbUKi0SRoKTmZsyyCBlskNWvdSTa4foVvQp44wRnH21FHo/hyCMIX/2OJY69GO66INV7gjEC6XcBU/fqOw=='],
        [u'교양', 'MfaFitBzr0yR9R5gSqtb+uLLEfd/vfsC1zoqZAz5T+KlSihDrDwtHWk8Z0eLHNY9srtHbiGkFHtDergzRdKoqw=='],
        [u'어린이', '2z61qoJV1edZ7wYxHifQhyZ/3InC2IpnjKD7jNT8EPWgmue7x/3XhFhW2paRfV3xpuz4iYca/uL7ve8TxvxlPQ=='],
    ]},
    { 'type' : 'share_ftv', 'name' : u'외국TV(종영)', 'list' : [
        [u'미드', 'bHVNM4AGa97w+2FyVnm+VVzLoKABmVPkw7n9MKBVGGlYeMbCIVZVJxx0eVla6/HUgsKPgEQoAsLaPomXfi4hYg=='],
        [u'일드', 'P5FWMumhVh3O8ZF28pfKWSo6369bmJ3eSdbG0dlhOSPQwgLe6GjEsHL1JWOQaebg+7gzGJpyy2dfhlSy09BAtQ=='],
        [u'중드', 'ql9h28mK4z+oiDPoX40Olr2ZD/ZEPZQMg6cDhjH4IUR+RGF7aaWGJ61+Czs3MrF6Xwx5TBI9ojM3UyY+V3aPgg=='],
        [u'영드', 'i0zTjWaVHSvs7gGmDvMTTk5vxB2k7Q6tl3+PRMRWxzfA2DQFPxORU61yRmGu42GbSZZlIWifjHXOLhWy4N+Nxw=='],
        [u'다큐', '+NCMKzYZ/nExNICfcJNGiYWgnOvv7Y46z9ZvzcosQrlecgXojpt88+g079dh5qh4jSsp3bZ0cebRXuFTVmQcMw=='],
        [u'애니', 'TSrz92ELuunV/w+V9bidX5BMs5Q+9AFXi8FhGr90cFNOyXsHHcaJrofFyvM0yiVFljAb3ADIoHje0sxg/V9NMA=='],
        [u'더빙', 'TCKh+GXEKJ+Iq4Kttkr9N01ql+CFegL0IK/klxawqhXrAPgZfvMi8mqVA5R+MY8xsp/YNjrjbgxKgd4dI9k8kQ=='],
        [u'기타', 'jmV/xj8ocJXyjcErMqMv9QvM7TwhXWDGXTx9q3NLPyAcQikcRlZPuXxoOZLh7aLMqtvV0imkFqtvfQSoWp+Wgw=='],
    ]},
    { 'type' : 'share_etc', 'name' : u'기타', 'list' : [
        #[u'전체', 'dsm4G8aizyDJ+8VHHU7OIs6gQcrcBoiHSfh37znDcbKJLPcXqIllSDSYzuFFy+j675yNX+4tMCPvsHdxZZ0mGw=='],
        [u'영상', 'c7sXC6+8vX7bnMeMS4X6pua9dCMoscokm3Zp2OHA4Cfj72/9Tk0/MVpPxp8N4LsRX2DLE7Q5L5VL0kE+kkpG+w=='],
        [u'음악', 'GN0gqbjMc+UjSDYu9IdJGLrlk7Oib8BM+eAJNLpDlmh9bFpO24TCB8Z6Ory5z2pBmMYMNv1YWxdmNYtJz7GIxA=='],
        [u'SW', 'lDbIydMTTDHbGraHDU7QLQeMPFe/XVuw23oa3heuxXPx8fnhSNeBGJeYXfvp3/uQsWa6/KBm0BbLrJlHqzs0vQ=='],
        [u'기타', '8EwvmvMsldeg80cxZvAhr7tZEB4ASlBWo6HeE5iZ4Rph0ymxd/vlXxiifbR7n19YTUaspxlJEAyCuEq5cfPJWg=='],
    ]},
    { 'type' : 'share_private', 'name' : u'등록안함', 'list' : [
        [u'전체', 'MlqqdV/Rh9AJqVCSKBU2sOxH0j5f7oOkP4ZYPTph2botAwfdbMNPQo/73zT/Tcp6BcOdVRdiV27tuY8KGNq2aQ=='], 
    ]},
]

class LogicUser(object):
    @staticmethod
    def process_ajax(sub, req):
        try:
            if sub == 'category_list':
                return jsonify(category_list)
            elif sub == 'get_daum_info':
                title = req.form['board_title']
                board_type = req.form['board_type']
                ret = LogicUser.daum_info(title, board_type)
                return jsonify(ret)
            elif sub == 'search_plex':
                keyword = req.form['keyword']
                ret = LogicUser.search_plex(keyword)
                return jsonify(ret)
            elif sub == 'do_action':
                ret = LogicUser.do_action(req)
                return jsonify(ret)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def process_api(sub, req):
        try:
            if sub == 'copy':
                folder_id = req.form['folder_id']
                folder_name = req.form['folder_name']
                board_type = req.form['board_type']
                category_type = req.form['category_type']
                size = int(req.form['size'])

                my_remote_path = LogicUser.copy(folder_id, folder_name, size, board_type, category_type,)
                ret = {}
                if my_remote_path is None:
                    ret['ret'] = 'fail'
                    ret['data'] = 'remote path is None!!'
                else:
                    ret['ret'] = 'success'
                    ret['data'] = my_remote_path
                return jsonify(ret)
            elif sub == 'torrent_copy':
                folder_id = req.form['folder_id']
                board_type = req.form['board_type']
                category_type = req.form['category_type']

                my_remote_path = LogicUser.torrent_copy(folder_id, board_type, category_type, show_modal=True)
                ret = {}
                if my_remote_path is None:
                    ret['ret'] = 'fail'
                    ret['data'] = 'remote path is None!!'
                else:
                    ret['ret'] = 'success'
                    ret['data'] = my_remote_path
                return jsonify(ret)
            elif sub == 'vod_copy':
                fileid = req.form['fileid']
                board_type = req.form['board_type']
                category_type = req.form['category_type']
                my_remote_path = LogicUser.get_my_copy_path(board_type, category_type)
                ret = {}
                if my_remote_path is None:
                    ret['ret'] = 'fail'
                    ret['data'] = 'remote path is None!!'
                else:
                    ret['ret'] = 'success'
                    ret['data'] = my_remote_path
                    LogicUser.vod_copy(fileid, my_remote_path)
                return jsonify(ret)
            elif sub == 'copy_with_json':
                fileid = req.form['fileid']
                board_type = req.form['board_type']
                category_type = req.form['category_type']
                my_remote_path = LogicUser.get_my_copy_path(board_type, category_type)
                my_remote_path = LogicUser.copy_with_json(fileid, my_remote_path, show_modal=True)
                ret = {}
                if my_remote_path is None:
                    ret['ret'] = 'fail'
                    ret['data'] = 'remote path is None!!'
                else:
                    ret['ret'] = 'success'
                    ret['data'] = my_remote_path
                return jsonify(ret)


        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################
    @staticmethod
    def daum_info(title, board_type):
        try:
            if board_type == 'share_movie':
                from framework.common.daum import MovieSearch
                match = re.compile(r'\(\d{4}\)').search(title)
                year = ''
                if match:
                    title = title.replace(match.group(0), '').strip()
                    year = match.group(0).replace('(', '').replace(')', '')
                data = MovieSearch.search_movie(title, year)
                data = data[1][0]
                data['daum_url'] = 'https://movie.daum.net/moviedb/main?movieId=' + data['id']
            elif board_type == 'share_ktv' or board_type == 'share_ftv':
                from framework.common.daum import DaumTV
                match = re.compile(r'\(\d{4}\)').search(title)
                year = ''
                if match:
                    title = title.replace(match.group(0), '').strip()
                    year = match.group(0).replace('(', '').replace(')', '')
                data = DaumTV.get_daum_tv_info(title)
                data['episode_list'] = []
                data['daum_url'] = 'https://search.daum.net/search?w=tv&q=%s&irk=%s' % (data['title'], data['daum_id'])
            return data
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return ''


    @staticmethod
    def do_action(req):
        try:
            logger.debug(req.form)
            #return
            folder_id = req.form['folder_id']
            my_remote_path = req.form['my_remote_path']
            
            # 게시판
            board_type = req.form['board_type']
            category_type = req.form['category_type']
            board_title = req.form['board_title']
            board_content = req.form['board_content']
            board_daum_url = req.form['board_daum_url']
            folder_name = req.form['folder_name'] 

            size = int(req.form['size'])
            daum_info = req.form['daum_info']
            action = req.form['action']
            user_id = SystemModelSetting.get('sjva_me_user_id')
            if board_content.startswith('ID:'):
                user_id = board_content.split('\n')[0].split(':')[1].strip()
                board_content = board_content[board_content.find('\n'):]


            def func():
                ret = RcloneTool.do_action(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), action, 'category', folder_id, folder_name, '', my_remote_path, 'real', folder_id_encrypted=True, listener=None, force_remote_name=ModelSetting.get('force_remote_name'))

                msg = u'Percent : %s\n' % ret['percent']
                socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                #msg = u'폴더ID : %s\n' % ret['folder_id']
                #socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)

                if ret['percent'] == 100:
                    msg = u'업로드 크기 적용..\n'
                    socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                    tmp = ModelSetting.get_int('size_upload')
                    tmp += size
                    ModelSetting.set('size_upload', str(tmp))
                    logger.debug('폴더ID:%s', ret['folder_id'])
                    if board_type != 'share_private' and ret['folder_id'] != '':
                        msg = u'게시물 등록중...\n'
                        socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        
                        data = {'board_type' : board_type, 'category_type':category_type, 'board_title':board_title, 'board_content':board_content, 'board_daum_url' : board_daum_url, 'folder_name':folder_name, 'size':size, 'daum_info':daum_info, 'folder_id':ret['folder_id'], 'user_id':user_id, 'lsjson' : json.dumps(ret['lsjson'])}
                        LogicUser.site_append(data)
                    else:
                        msg = u'업로드한 폴더ID값을 가져올 수 없어서 사이트 등록에 실패하였습니다.\n관리자에게 등록 요청하세요.\n'
                        socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                msg = u'모두 완료되었습니다.\n'
                socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)

            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return ''
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def site_append(data):
        try:
            import requests
            import json
            response = requests.post("https://sjva.me/sjva/share_append.php", data={'data':json.dumps(data)})
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def copy(folder_id, folder_name, size, board_type, category_type):
        try:
            my_remote_path = LogicUser.get_my_copy_path(board_type, category_type)
            if my_remote_path is None:
                return
            #if my_remote_path.startswith('gc:'):
            #    try:
            #        from rclone_expand.logic_gclone import LogicGclone
            #        tmp = ['gc:{%s}|%s/%s' % (RcloneTool.folderid_decrypt(folder_id), my_remote_path, folder_name)]
            #        LogicGclone.queue_append(tmp)
            #    except Exception as e: 
            #        logger.error('Exception:%s', e)
            #        logger.error(traceback.format_exc())
            #else:
            def func():
                ret = RcloneTool.do_action(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'),  'download', '', folder_id, folder_name, '', my_remote_path, 'real', folder_id_encrypted=True, listener=None, show_modal=ModelSetting.get_bool('show_modal'), option=ModelSetting.get_list('user_option', ' '), force_remote_name=ModelSetting.get('force_remote_name'))

                if ret['percent'] == 100:
                    tmp = ModelSetting.get_int('size_download')
                    tmp += size
                    ModelSetting.set('size_download', str(tmp))

                msg = u'모두 완료되었습니다.'
                socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)

            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return my_remote_path
            
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def torrent_copy(folder_id, board_type, category_type, my_remote_path=None, callback=None, callback_id=None, show_modal=False):
        try:
            if my_remote_path is None:
                my_remote_path = LogicUser.get_my_copy_path(board_type, category_type)
            if my_remote_path is None:
                return
            # 시간차이가 있어서 바로 다운로드가 안되는 문제 발생
            # 폴더id의 내용이 있는지 확인
            
            #if my_remote_path.startswith('gc:'):
            #    try:
            #        from rclone_expand.logic_gclone import LogicGclone
            #        tmp = ['gc:{%s}|%s' % (RcloneTool.folderid_decrypt(folder_id), my_remote_path)]
            #        LogicGclone.queue_append(tmp)
            #    except Exception as e: 
            #        logger.error('Exception:%s', e)
            #        logger.error(traceback.format_exc())
            #    return 'gclone'
            #else:
            def func():
                for i in range(1, 11):
                    logger.debug('토렌트 다운로드 시도 : %s %s', i, folder_id)
                    ret = RcloneTool.do_action(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'),  'download', '', folder_id, '', '', my_remote_path, 'real', folder_id_encrypted=True, listener=None, show_modal=show_modal, force_remote_name=ModelSetting.get('force_remote_name'))
                    #logger.debug(ret)
                    if ret['percent'] == 0:
                        if show_modal:
                            msg = u'아직 토렌트 파일을 받지 못했습니다. 30초 후 다시 시도합니다. (%s/10)' % i
                            socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        time.sleep(30)
                    else:
                        if show_modal:
                            msg = u'모두 완료되었습니다.'
                            socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        if callback is not None:
                            callback(callback_id)
                        break
                    #logger.debug(msg)
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return 'rclone'
            #return my_remote_path
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_my_copy_path(board_type, category_type):
        try:
            tmp = ModelSetting.get_list('user_copy_dest_list', '\n')
            remote_list = {}
            for t in tmp:
                t2 = t.split('=')
                if len(t2) == 2 and t2[1].strip() != '':
                    remote_list[t2[0].strip()] = t2[1].strip()
            keys = [u'%s,%s' % (board_type, category_type), u'%s' % (board_type), 'default']

            for key in keys:
                if key in remote_list:
                    return remote_list[key]
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_remote_path(filepath):
        try:
            rule = ModelSetting.get('user_plex_match_rule')
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
    def search_plex(keyword):
        import plex
        try:
            data = plex.LogicNormal.find_by_filename_part(keyword)
            ret  = dict()
            ndirs  = 0
            nfiles = 0
            #logger.debug(data)
            if len(data['list']) > 0:
                for item in data['list']:
                    if item['dir'] in ret:
                        f = ret[item['dir']]['files']
                        f.append({'filename': item['filename'], 'size_str':item['size_str']})
                    else:
                        remote_path = LogicUser.get_remote_path(item['dir'])
                        ret[item['dir']] = {'remote_path': remote_path, 'files': [{'filename': item['filename'], 'size_str':item['size_str']}]}

                ndirs = len(ret)
                for k, v in ret.items(): nfiles = nfiles + len(v['files'])
            logger.debug('search plex: keyword(%s), result(%d dirs, %d files)', keyword, ndirs, nfiles)
            return ret

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def vod_copy(fileid, remote_path):
        try:
            if remote_path is None:
                return
            def func():
                for i in range(1, 11):
                    logger.debug('VOD 다운로드 시도 : %s %s', i, fileid)
                    ret = RcloneTool.fileid_copy(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), fileid, remote_path)
                    if ret:
                        break
                    time.sleep(30)
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())






    @staticmethod
    def copy_with_json(fileid, my_remote_path, show_modal=False):
        try:
            if my_remote_path is None:
                return
            
            def func():
                #for i in range(1, 11):
                    #ret = RcloneTool.do_action(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'),  'download', '', folder_id, '', '', my_remote_path, 'real', folder_id_encrypted=True, listener=None, show_modal=show_modal, force_remote_name=ModelSetting.get('force_remote_name'))

                    ret = RcloneTool.copy_with_json(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), fileid, my_remote_path,  show_modal=show_modal)

                    #logger.debug(ret)
                    """
                    if ret['percent'] == 0:
                        if show_modal:
                            msg = u'아직 토렌트 파일을 받지 못했습니다. 30초 후 다시 시도합니다. (%s/10)' % i
                            socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        time.sleep(30)
                    else:
                        if show_modal:
                            msg = u'모두 완료되었습니다.'
                            socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        if callback is not None:
                            callback(callback_id)
                        break
                    """
                    #logger.debug(msg)
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return my_remote_path
            #return my_remote_path
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

