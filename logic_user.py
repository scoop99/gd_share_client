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
from sqlalchemy import or_, and_, func, not_, desc

# sjva 공용
from framework import app, db, scheduler, path_app_root, socketio
from framework.job import Job
from framework.util import Util
from framework.common.share import RcloneTool, RcloneTool2
from system.model import ModelSetting as SystemModelSetting
from framework.common.plugin import LogicModuleBase
# 패키지
from .plugin import P, logger, package_name, ModelSetting

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



class LogicUser(LogicModuleBase):
    db_default = { 
        'user_copy_dest_list' : u'default = \nshare_movie,국내 = \nshare_movie,외국 = \nshare_ktv,드라마 = \nshare_ktv,예능 = \nshare_ktv,교양 = \nshare_ftv = \nshare_etc = ',
        'user_plex_match_rule': '',
    }

    def __init__(self, P):
        super(LogicUser, self).__init__(P, 'list')
        self.name = 'user'

         


    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        
        if P.plugin_small:
            sub = 'setting'
        if sub in ['setting', 'upload', 'list']:
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            if sub == 'category_list':
                return jsonify(category_list)
            elif sub == 'get_daum_info':
                title = req.form['board_title']
                board_type = req.form['board_type']
                ret = self.daum_info(title, board_type)
                return jsonify(ret)
            elif sub == 'search_plex':
                keyword = req.form['keyword']
                ret = LogicUser.search_plex(keyword)
                return jsonify(ret)
            elif sub == 'do_action':
                ret = self.do_action(req)
                return jsonify(ret)
            elif sub == 'web_list':
                return jsonify(ModelShareItem.web_list(req))
            elif sub == 'db_remove':
                return jsonify(ModelShareItem.delete_by_id(req.form['id']))
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    def process_api(self, sub, req):
        try:
            if sub == 'add_copy':
                folder_id = req.form['folder_id']
                folder_name = req.form['folder_name']
                board_type = req.form['board_type']
                category_type = req.form['category_type']
                size = int(req.form['size'])
                count = int(req.form['count'])
                ddns = req.form['ddns']
                if ddns != SystemModelSetting.get('ddns'):
                    ret = {'ret':'wrong_ddns'}
                else:
                    ret = self.add_copy(folder_id, folder_name, board_type, category_type, size, count)
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


    def process_normal(self, sub, req):
        try:
            if sub == 'copy_completed':
                clone_folder_id = req.form['clone_folder_id']
                client_db_id = req.form['client_db_id']

                self.do_download(client_db_id, clone_folder_id)
                ret = {'ret':'success'}
                return jsonify(ret)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################

    def daum_info(self, title, board_type):
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






    def do_action(self, req):
        try:
            upload_folderid = '1HgFbtNtWOUZPaG9VaW032VgF64aEgIiF'
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
                ret = RcloneTool2.do_user_upload(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), my_remote_path, folder_name, '1HgFbtNtWOUZPaG9VaW032VgF64aEgIiF', board_type, category_type)

                if ret['completed']:
                    if board_type != 'share_private' and ret['folder_id'] != '':
                        msg = u'6. 게시물 등록중...\n'
                        socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        data = {'board_type' : board_type, 'category_type':category_type, 'board_title':board_title, 'board_content':board_content, 'board_daum_url' : board_daum_url, 'folder_name':folder_name, 'size':ret['size'], 'daum_info':daum_info, 'folder_id':ret['folder_id'], 'user_id':user_id, 'lsjson' : json.dumps(ret['lsjson'])}
                        LogicUser.site_append(data)
                    else:
                        msg = u'업로드한 폴더ID값을 가져올 수 없어서 사이트 등록에 실패하였습니다.\n관리자에게 등록 요청하세요.\n'
                        socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                else:
                    socketio.emit("command_modal_add_text", u'업로드가 완료되지 않아 게시글이 등록되지 않습니다.\n', namespace='/framework', broadcast=True)
                    socketio.emit("command_modal_add_text", u'확인 후 다시 시도하세요.\n', namespace='/framework', broadcast=True)
                socketio.emit("command_modal_add_text", u'\n모두 완료되었습니다.\n', namespace='/framework', broadcast=True)
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return ''
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    def get_my_copy_path(self, board_type, category_type):
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


    def add_copy(self, folder_id, folder_name, board_type, category_type, size, count):
        try:
            ret = {'ret':'fail', 'remote_path':None, 'server_response':None}
            ret['remote_path'] = self.get_my_copy_path(board_type, category_type)
            if ret['remote_path'] is None:
                return ret

            item = ModelShareItem.get_by_source_id(folder_id)
            if item is not None:
                ret['ret'] = 'already'
                ret['status'] = item.status
                return ret
            
            can_use_share_flag = RcloneTool2.can_use_share(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), ret['remote_path'])
            if not can_use_share_flag:
                ret['ret'] = 'cannot_access'
                return ret
            
            
            
            item = ModelShareItem()
            item.copy_type = 'share'
            item.source_id = folder_id
            item.target_name = folder_name
            item.board_type = board_type
            item.category_type = category_type
            item.size = size
            item.count = count
            item.remote_path = ret['remote_path']
            item.save()

            data = item.as_dict()
            data['ddns'] = SystemModelSetting.get('ddns')
            data['sjva_me_id'] = SystemModelSetting.get('sjva_me_user_id')
            url = P.SERVER_URL + '/gd_share_server/noapi/user/request'
            res = requests.post(url, data={'data':json.dumps(data)})

            ret['server_response'] = res.json()
            if 'db_id' in ret['server_response']:
                item.status = 'request'
                item.request_time = datetime.now()
                item.save()
            ret['ret'] = 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = 'fail'
            ret['log'] = str(e)

        logger.debug(ret)
        return ret



    def do_download(self, db_id, clone_folder_id):
        def func():
            try:
                item = ModelShareItem.get_by_id(int(db_id))
                if item is None:
                    logger.error('CRITICAL ERROR:%s', db_id)
                    return
                item.status = 'clone'
                item.clone_completed_time = datetime.now()
                item.clone_folderid = clone_folder_id
                #item.save()

                ret = RcloneTool2.do_user_download(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), item.clone_folderid, item.remote_path)

                if ret:
                    item.status = 'completed'
                    item.completed_time = datetime.now()
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
            finally:
                if item is not None:
                    item.save()
        thread = threading.Thread(target=func, args=())
        thread.setDaemon(True)
        thread.start()



    @staticmethod
    def site_append(data):
        try:
            import requests
            import json
            response = requests.post("https://sjva.me/sjva/share_append2.php", data={'data':json.dumps(data)})
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























class ModelShareItem(db.Model):
    __tablename__ = '{package_name}_item'.format(package_name=P.package_name)
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = P.package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    copy_type = db.Column(db.String) # folder, file
    source_id = db.Column(db.String)
    target_name = db.Column(db.String) # 폴더면 폴더명, 파일이면 파일명

    call_from = db.Column(db.String)
    board_type = db.Column(db.String)
    category_type = db.Column(db.String)
    remote_path = db.Column(db.String) 
    size = db.Column(db.Integer)
    count = db.Column(db.Integer)

    status = db.Column(db.String) # 'ready' 'request' 'clone' 'completed'
    clone_completed_time = db.Column(db.DateTime)
    completed_time = db.Column(db.DateTime)
    request_time = db.Column(db.DateTime)

    clone_folderid = db.Column(db.String) 


    def __init__(self):
        self.created_time = datetime.now()
        self.status = 'ready'

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%Y-%m-%d %H:%M:%S') 
        ret['clone_completed_time'] = self.clone_completed_time.strftime('%Y-%m-%d %H:%M:%S') if self.clone_completed_time is not None else None
        ret['completed_time'] = self.completed_time.strftime('%Y-%m-%d %H:%M:%S') if self.completed_time is not None else None
        ret['request_time'] = self.request_time.strftime('%Y-%m-%d %H:%M:%S') if self.request_time is not None else None
        return ret

    def save(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def get_by_id(cls, id):
        return db.session.query(cls).filter_by(id=id).first()

    @classmethod
    def delete_by_id(cls, id):
        db.session.query(cls).filter_by(id=id).delete()
        db.session.commit()
        return True

    @classmethod
    def get_by_source_id(cls, source_id):
        return db.session.query(cls).filter_by(source_id=source_id).first()
    
    



    @classmethod
    def web_list(cls, req):
        ret = {}
        page = int(req.form['page']) if 'page' in req.form else 1
        page_size = 30
        job_id = ''
        search = req.form['search_word'] if 'search_word' in req.form else ''
        option = req.form['option'] if 'option' in req.form else 'all'
        order = req.form['order'] if 'order' in req.form else 'desc'
        query = cls.make_query(search=search, order=order, option=option)
        count = query.count()
        query = query.limit(page_size).offset((page-1)*page_size)
        lists = query.all()
        ret['list'] = [item.as_dict() for item in lists]
        ret['paging'] = Util.get_paging_info(count, page, page_size)
        return ret


    @classmethod
    def make_query(cls, search='', order='desc', option='all'):
        query = db.session.query(cls)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(cls.target_name.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(cls.target_name.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(cls.target_name.like('%'+search+'%'))
        if option == 'completed':
            query = query.filter(cls.status == 'completed')

        query = query.order_by(desc(cls.id)) if order == 'desc' else query.order_by(cls.id)
        return query  

    @classmethod
    def get_list_incompleted(cls):
        return db.session.query(cls).filter(cls.status != 'completed').all()

    @classmethod
    def append(cls, q):
        item = ModelShareItem()
        item.source_id = q['folder_id']
        item.season = q['season']
        item.episode_no = q['epi_queue']
        item.title = q['content_title']
        item.episode_title = q['title']
        item.ani365_va = q['va']
        item.ani365_vi = q['_vi']
        item.ani365_id = q['_id']
        item.quality = q['quality']
        item.filepath = q['filepath']
        item.filename = q['filename']
        item.savepath = q['savepath']
        item.video_url = q['url']
        item.vtt_url = q['vtt']
        item.thumbnail = q['thumbnail']
        item.status = 'wait'
        item.ani365_info = q['ani365_info']
        item.save()

