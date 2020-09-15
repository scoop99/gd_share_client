# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback

# third-party
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, session, send_from_directory 
from flask_socketio import SocketIO, emit, send
from flask_login import login_user, logout_user, current_user, login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_data, socketio, check_api
from framework.util import Util
from framework.common.plugin import get_model_setting, Logic, default_route
#########################################################

class P(object):
    package_name = __name__.split('.')[0]
    logger = get_logger(package_name)
    blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    menu = {
        'main' : [package_name, '구글 드라이브 공유'], 
        'sub' : [
            ['base', '기본'], ['user', '유저공유'], ['log', '로그']
        ],
        'category' : 'service',
        'sub2' : {
            'base' : [
                ['setting', '기본 설정'], #['list', '목록']
            ],
            #'av_sub' : [
            #    ['setting', '설정'], ['list', '목록'], ['detail', '세부정보'], ['transfer', '전송'], ['plex', 'PLEX에서 찾기']
            #],
            'user' : [
                ['setting', '설정'], ['upload', '업로드'], ['list', '작업현황'] #['download_list', '다운로드 목록'],
            ]
        },
    }
    plugin_info = {
        'version' : '0.2.0.0',
        'name' : 'gd_share_client',
        'category_name' : 'service',
        'developer' : 'soju6jan',
        'description' : '구글 드라이브 공유 클라이언트',
        'home' : 'https://github.com/soju6jan/gd_share_client',
        'more' : '',
        'policy_level' : 3,
    }
    ModelSetting = get_model_setting(package_name, logger)
    logic = None
    module_list = None
    home_module = 'user'
    SERVER_URL = 'https://sjva-dev.soju6jan.com'
    plugin_small = None

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting


def initialize():
    try:
        app.config['SQLALCHEMY_BINDS'][P.package_name] = 'sqlite:///%s' % (os.path.join(path_data, 'db', '{package_name}.db'.format(package_name=P.package_name)))
        from framework.util import Util
        Util.save_from_dict_to_json(P.plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        from .logic_base import LogicBase
        from .logic_user import LogicUser
        P.module_list = [LogicBase(P), LogicUser(P)]
        P.logic = Logic(P)
        default_route(P)

        plugin_small = True if app.config['config']['level'] < 4 else False
        if plugin_small:
            del(P.menu['sub'][2])
            del(P.menu['sub2']['user'][1])
    except Exception as e: 
        P.logger.error('Exception:%s', e)
        P.logger.error(traceback.format_exc())

initialize()

"""
from .model import ModelSetting
from .logic import Logic
from .logic_av_sub import LogicAVSub



def plugin_load():
    Logic.plugin_load()

def plugin_unload():
    Logic.plugin_unload()

def process_telegram_data(data):
    Logic.process_telegram_data(data)


#########################################################
# WEB Menu   
#########################################################


@blueprint.route('/<sub>', methods=['GET', 'POST'])
@login_required
def first_menu(sub): 
    logger.debug('FM: sub(%s)', sub)
    try:
        if sub == 'base':
           return redirect('/%s/%s/setting' % (package_name, sub))
        elif sub == 'av_sub':
            return redirect('/%s/%s/setting' % (package_name, sub))
        elif sub == 'user':
            if plugin_small:
                return redirect('/%s/%s/setting' % (package_name, sub))
            return redirect('/%s/%s/upload' % (package_name, sub))
        elif sub == 'log':
            return render_template('log.html', package=package_name)
        return render_template('sample.html', title='%s - %s' % (package_name, sub))
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())


@blueprint.route('/<sub>/<sub2>', methods=['GET', 'POST'])
@login_required
def second_menu(sub, sub2):
    try:
        arg = ModelSetting.to_dict()
        job_id = '%s_%s' % (package_name, sub)
        if sub == 'base':
            arg['sub'] = sub
            if sub2 == 'setting':
                arg['size_upload'] = Util.sizeof_fmt(ModelSetting.get_int('size_upload'), suffix='B')
                arg['size_download'] = Util.sizeof_fmt(ModelSetting.get_int('size_download'), suffix='B')
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
        elif sub == 'av_sub':
            arg['sub'] = sub
            if sub2 == 'setting':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'list':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'detail':
                if 'folder_name' in request.form:
                    arg['folder_name'] = request.form['folder_name']
                    ModelSetting.set('av_sub_folder_name', arg['folder_name'])
                else:
                    arg['folder_name'] = ModelSetting.get('av_sub_folder_name')
                try:
                    from plex.model import ModelSetting as PlexModelSetting
                    arg['plex_url'] = PlexModelSetting.get('server_url')
                    arg['plex_machineIdentifier'] = PlexModelSetting.get('machineIdentifier')
                except:
                    pass
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'transfer':
                arg['mode'] = None if 'mode' not in request.form else request.form['mode']
                arg['server_type'] = None if 'mode' not in request.form else request.form['server_type']
                #arg['folder_id'] = 'zn4TpiHrBMtj8/S4j2q6WcUm8C2jB7YxzVaHI0M9lElk17NZKT1JjZ6Zkhe3ruFIfmPtBhpnSgmxsH2xTqZb6w==' if 'folder_id' not in request.form else request.form['folder_id']
                arg['folder_id'] = '' if 'folder_id' not in request.form else request.form['folder_id']
                arg['folder_name'] = '' if 'folder_name' not in request.form else request.form['folder_name']
                arg['server_filename'] = '' if 'server_filename' not in request.form else request.form['server_filename']
                arg['defalut_remote_path'] = arg['defalut_remote_path'] if 'remote_path' not in request.form or request.form['remote_path'] == '' else request.form['remote_path']
                # 2020-07-23 by soju
                # server_filename == '' 인 경우가 폴더채다운로드. server_filename 파일명이 있다면 이미 맞는 remote_path
                if ModelSetting.get_bool('av_sub_library_match') and arg['mode'] == 'download' and arg['server_filename'] == '':
                    arg['defalut_remote_path'] = LogicAVSub.get_download_remote_path(arg['folder_name'])
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'plex':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
        elif sub == 'user':
            arg['sub'] = sub
            if sub2 == 'setting':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'upload':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
            elif sub2 == 'list':
                return render_template('{package_name}_{sub}_{sub2}.html'.format(package_name=package_name, sub=sub, sub2=sub2), arg=arg)
        return render_template('sample.html', title='%s - %s' % (package_name, sub))
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())
    

#########################################################
# For UI                                                          
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    logger.debug('AJAX %s %s', package_name, sub)
    try:
        # global
        if sub == 'setting_save':
            ret = ModelSetting.setting_save(request)
            return jsonify(ret)
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())  


@blueprint.route('/ajax/<sub>/<sub2>', methods=['GET', 'POST'])
@login_required
def second_ajax(sub, sub2):
    try:
        if sub == 'base':
            return LogicBase.process_ajax(sub2, request)
        if sub == 'av_sub':
            return LogicAVSub.process_ajax(sub2, request)
        elif sub == 'user':
            return LogicUser.process_ajax(sub2, request)
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())


#########################################################
# API - 외부
#########################################################
@blueprint.route('/api/<sub>/<sub2>', methods=['GET', 'POST'])
@check_api
def api(sub, sub2):
    try:
        #sjva.me 에서 콜
        if sub == 'user':
            return LogicUser.process_api(sub2, request)
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

"""
