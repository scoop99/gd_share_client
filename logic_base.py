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
from framework import app, db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util
from framework.common.share import RcloneTool
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name, SERVER_URL
from .logic import Logic
from .model import ModelSetting

#########################################################
 
class LogicBase(object):
    @staticmethod
    def process_ajax(sub, req):
        try:
            if sub == 'rclone_lsjson':
                remote_path = req.form['remote_path']
                ret = RcloneTool.lsjson(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), remote_path)
                return jsonify(ret)
            elif sub == 'rclone_size':
                remote_path = req.form['remote_path']
                ret = RcloneTool.size(ModelSetting.get('rclone_path'), ModelSetting.get('rclone_config_path'), remote_path)
                return jsonify(ret)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    #################################################################
