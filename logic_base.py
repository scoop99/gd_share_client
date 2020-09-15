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
from framework import app, db, scheduler, path_app_root, path_data
from framework.job import Job
from framework.util import Util
from framework.common.share import RcloneTool
from framework.common.plugin import LogicModuleBase

# 패키지
from .plugin import P, logger, package_name,  ModelSetting
#########################################################
 
class LogicBase(LogicModuleBase):
    db_default = { 
        'db_version' : '5',
        'rclone_path' : os.path.join(path_app_root, 'bin', platform.system(), 'rclone'),
        'rclone_config_path' : os.path.join(path_data, 'db', 'rclone.conf'),
        'defalut_remote_path' : '',
    }


    def __init__(self, P):
        super(LogicBase, self).__init__(P, 'setting')
        self.name = 'base'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        if sub == 'setting':
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            if sub == 'rclone_lsjson':
                remote_path = req.form['remote_path']
                ret = RcloneTool.lsjson(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), remote_path)
                return jsonify(ret)
            elif sub == 'rclone_size':
                remote_path = req.form['remote_path']
                ret = RcloneTool.size(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), remote_path)
                return jsonify(ret)
            elif sub == 'conf_get':
                rclone_config_path = req.form['rclone_config_path']
                from framework.common.util import read_file
                ret = {'ret':False, 'data':''}
                if os.path.exists(rclone_config_path):
                    ret['ret'] = True
                    ret['data'] = read_file(rclone_config_path)
                return jsonify(ret)
            elif sub == 'conf_save':
                rclone_config_path = req.form['rclone_config_path']
                data = req.form['conf_text']
                data = data.replace("\r\n", "\n" ).replace( "\r", "\n" )
                with open(rclone_config_path, 'w') as f: 
                    f.write(data)
                return jsonify(True)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################
