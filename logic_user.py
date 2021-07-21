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
from framework import app, db, scheduler, path_app_root, socketio, version
from framework.job import Job
from framework.util import Util
from framework.common.share import RcloneTool, RcloneTool2
from system.model import ModelSetting as SystemModelSetting
from framework.common.plugin import LogicModuleBase
# 패키지
from .plugin import P, logger, package_name, ModelSetting

#########################################################

category_list = [
    { 'type' : 'share_movie', 'name' : u'영화', 'category_list' : [u'국내', u'외국', u'최신', u'더빙', u'최고품질', '3D']},
    { 'type' : 'share_ktv', 'name' : u'국내TV', 'category_list' : [u'드라마', u'예능', u'교양', u'어린이', u'기타']},
    { 'type' : 'share_ftv', 'name' : u'외국TV', 'category_list' : [u'미드', u'일드', u'중드', u'영드', u'다큐', u'애니', u'더빙', u'기타', u'방영중']},
    { 'type' : 'share_etc', 'name' : u'기타', 'category_list' : [u'영상', u'음악', u'SW', u'리딩', u'기타']},
]

class LogicUser(LogicModuleBase):
    instance = None
    db_default = { 
        'user_copy_dest_list' : u'default = \nshare_movie,국내 = \nshare_movie,외국 = \nshare_ktv,드라마 = \nshare_ktv,예능 = \nshare_ktv,교양 = \nshare_ftv = \nshare_etc = ',
        'user_upload_search_local': 'False',
        'user_plex_match_rule': '',
        'user_last_list_option' : '',
    }

    def __init__(self, P):
        super(LogicUser, self).__init__(P, 'list')
        self.name = 'user'
        LogicUser.instance = self
         

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
                ret = self.search_plex(keyword)
                return jsonify(ret)
            elif sub == 'do_action':
                ret = self.do_action(req)
                return jsonify(ret)
            elif sub == 'web_list':
                return jsonify(ModelShareItem.web_list(req))
            elif sub == 'db_remove':
                return jsonify(ModelShareItem.delete_by_id(req.form['id']))
            elif sub == 'add_copy_force':
                item_id = int(req.form['item_id'])
                ret = self.add_copy_force(item_id)
                return jsonify(ret)
           
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

                logger.debug(board_type)
                logger.debug(category_type)

                size = int(req.form['size'])
                count = int(req.form['count'])
                ddns = req.form['ddns']
                need_version = req.form['version']
                copy_type = req.form['copy_type']
                if ddns != SystemModelSetting.get('ddns'):
                    return {'ret':'wrong_ddns'}
                
                tmp1 = need_version.split('.')
                tmp2 = version.split('.')
                need_version = int(tmp1[2]) * 100 + int(tmp1[3])
                current_version = int(tmp2[2]) * 100 + int(tmp2[3])
                if need_version > current_version:
                    return {'ret':'need_update', 'current_version':version, 'need_version':need_version}
                ret = self.add_copy(folder_id, folder_name, board_type, category_type, size, count, copy_type=copy_type)
                ret['current_version'] = version

                logger.debug(ret)
                return jsonify(ret)
            elif sub == 'vod_copy':
                fileid = req.form['fileid']
                board_type = req.form['board_type']
                category_type = req.form['category_type']
                my_remote_path = self.get_my_copy_path(board_type, category_type)
                ret = {}
                if my_remote_path is None:
                    ret['ret'] = 'fail'
                    ret['data'] = 'remote path is None!!'
                else:
                    ret['ret'] = 'success'
                    ret['data'] = my_remote_path
                    self.vod_copy(fileid, my_remote_path)
                return jsonify(ret)

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    def process_normal(self, sub, req):
        try:
            if sub == 'copy_completed':
                clone_folder_id = req.form['clone_folder_id']
                client_db_id = req.form['client_db_id']
                logger.debug(f'copy_complted: {client_db_id}, {clone_folder_id}')
                self.do_download(client_db_id, clone_folder_id)
                ret = {'ret':'success'}
                return jsonify(ret)
            elif sub == 'callback':
                about = req.form['about']
                client_db_id = req.form['client_db_id']
                ret = req.form['ret']
                logger.debug('about : %s, client_db_id : %s, ret : %s', about, client_db_id, ret)
                if about == 'request':
                    item = ModelShareItem.get_by_id(int(client_db_id))
                    item.status = req.form['ret']
                    item.save()
                ret = {'ret':'success'}
                return jsonify(ret)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################


    def add_copy(self, folder_id, folder_name, board_type, category_type, size, count, copy_type='folder', remote_path=None):
        try:
            ret = {'ret':'fail', 'remote_path':remote_path, 'server_response':None}
            
            if ret['remote_path'] is None:
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
            
            """
            if board_type.startswith('bot_downloader') or board_type.startswith('torrent'):
                can_use_relay = RcloneTool2.can_use_relay(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), ModelSetting.get('worker_remote'))
                if not can_use_relay:
                    ret['ret'] = 'wrong_setting'
                    return ret
            """


            item = ModelShareItem()
            item.copy_type = copy_type
            item.source_id = folder_id
            item.target_name = folder_name
            item.board_type = board_type
            item.category_type = category_type
            item.size = size
            item.count = count
            item.remote_path = ret['remote_path']
            item.save()

            data = item.as_dict()
            #if board_type in ['bot_downloader_ktv', 'bot_downloader_movie', 'bot_downloader_av']:
            #    data['target_name'] = ''

            data['ddns'] = SystemModelSetting.get('ddns')
            data['sjva_me_id'] = SystemModelSetting.get('sjva_me_user_id')
            data['version'] = version
            url = P.SERVER_URL + '/gd_share_server/noapi/user/request'
            res = requests.post(url, data={'data':json.dumps(data)})

            ret['server_response'] = res.json()
            if ret['server_response']['ret'] == 'enqueue':
                if 'db_id' in ret['server_response'] and ret['server_response']['queue_name'] is not None:
                    item.status = 'request'
                    item.request_time = datetime.now()
                    item.save()
                    ret['ret'] = 'success'
            else:
                item.status = ret['server_response']['ret']
                #item.request_time = datetime.now()
                #item.save()
                ret['ret'] = ret['server_response']['ret']

            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = 'fail'
            ret['log'] = str(e)

        logger.debug(ret)
        return ret



    def add_copy_force(self, item_id):
        try:
            item = ModelShareItem.get_by_id(item_id)
            logger.debug(f'복사 재요청!!!!! {item_id}')
            ret = {'ret':'fail', 'remote_path':item.remote_path, 'server_response':None}
            can_use_share_flag = RcloneTool2.can_use_share(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), ret['remote_path'])
            if not can_use_share_flag:
                ret['ret'] = 'cannot_access'
                return ret

            data = item.as_dict()
            data['ddns'] = SystemModelSetting.get('ddns')
            data['sjva_me_id'] = SystemModelSetting.get('sjva_me_user_id')
            data['version'] = version
            url = P.SERVER_URL + '/gd_share_server/noapi/user/request'
            res = requests.post(url, data={'data':json.dumps(data)})

            ret['server_response'] = res.json()
            if ret['server_response']['ret'] == 'enqueue':
                if 'db_id' in ret['server_response'] and ret['server_response']['queue_name'] is not None:
                    item.status = 'request'
                    item.request_time = datetime.now()
                    item.save()
                    ret['ret'] = 'success'
            else:
                item.status = ret['server_response']['ret']
                ret['ret'] = ret['server_response']['ret']

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
                remote_path = item.remote_path
                """
                if is_relay:
                    remote_path = ModelSetting.get('worker_remote').rstrip('/') + ('/%s' % item.id)
                    ret = RcloneTool2.do_relay_download(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), item.clone_folderid, remote_path, item.source_id, item.remote_path)
                    #remote_path = item.remote_path + '/tmp_' + item.source_id
                else:
                """
                
                """
                change_parent_arg = None
                if item.board_type.startswith('share'):
                    change_parent_arg = item.target_name
                ret = RcloneTool2.do_user_download(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), item.clone_folderid, remote_path, change_parent_arg=change_parent_arg)
                """
                try:
                    for i in range(5):
                        size_data = RcloneTool2.size(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), '%s:{%s}' % (remote_path.split(':')[0], clone_folder_id))
                        logger.debug('size_data : %s, %s', i, size_data)
                        if size_data is None or size_data['count'] == 0:
                            time.sleep(30)
                        else:
                            break
                except Exception as e: 
                    logger.error('Exception:%s', e)
                    logger.error(traceback.format_exc())
                ret = RcloneTool2.do_user_download(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), item.clone_folderid, remote_path)

                if ret:
                    item.status = 'completed'
                    item.completed_time = datetime.now()
                else:
                    item.status = 'fail_move'
                    item.completed_time = datetime.now()
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
                item.status = 'fail_download_exception'
            finally:
                if item is not None:
                    item.save()
        thread = threading.Thread(target=func, args=())
        thread.setDaemon(True)
        thread.start()


    def vod_copy(self, fileid, remote_path):
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





    #################################################################
    # 업로드 관련
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
            upload_folderid = '1zO0FIExK4izwV93R0cYSZ13KW-TUVntC'
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
                ret = RcloneTool2.do_user_upload(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), my_remote_path, folder_name, upload_folderid, board_type, category_type, is_move=(action=='move'))

                if ret['completed']:
                    if board_type != 'share_private' and ret['folder_id'] != '':
                        msg = u'6. 게시물 등록중...\n'
                        socketio.emit("command_modal_add_text", str(msg), namespace='/framework', broadcast=True)
                        data = {'board_type' : board_type, 'category_type':category_type, 'board_title':board_title, 'board_content':board_content, 'board_daum_url' : board_daum_url, 'folder_name':folder_name, 'size':ret['size'], 'daum_info':daum_info, 'folder_id':ret['folder_id'], 'user_id':user_id, 'lsjson' : json.dumps(ret['lsjson'])}
                        self.site_append(data)
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
            tmp = ModelSetting.get_list('user_copy_dest_list', '\n', comment=None)
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


    def site_append(self, data):
        try:
            import requests
            import json
            response = requests.post("https://sjva.me/sjva/share_append2.php", data={'data':json.dumps(data)})
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    def search_plex(self, keyword):
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
                        remote_path = self.get_remote_path(item['dir'])
                        ret[item['dir']] = {'remote_path': remote_path, 'files': [{'filename': item['filename'], 'size_str':item['size_str']}]}

                ndirs = len(ret)
                for k, v in ret.items(): nfiles = nfiles + len(v['files'])
            logger.debug('search plex: keyword(%s), result(%d dirs, %d files)', keyword, ndirs, nfiles)
            return ret

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    def get_remote_path(self, filepath):
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
        option1 = req.form['option1'] if 'option1' in req.form else 'all'
        option2 = req.form['option2'] if 'option2' in req.form else 'all'
        order = req.form['order'] if 'order' in req.form else 'desc'
        query = cls.make_query(search=search, order=order, option1=option1, option2=option2)
        count = query.count()
        query = query.limit(page_size).offset((page-1)*page_size)
        lists = query.all()
        ret['list'] = [item.as_dict() for item in lists]
        ret['paging'] = Util.get_paging_info(count, page, page_size)
        ModelSetting.set('user_last_list_option', '%s|%s|%s|%s|%s' % (option1, option2, desc, search, page))
        return ret


    @classmethod
    def make_query(cls, search='', order='desc', option1='all', option2='all'):
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
        if option1 != 'all':
            query = query.filter(cls.board_type == option1)
        if option2 != 'all':
            query = query.filter(cls.status.like(option2 + '%'))
        query = query.order_by(desc(cls.id)) if order == 'desc' else query.order_by(cls.id)
        return query  
