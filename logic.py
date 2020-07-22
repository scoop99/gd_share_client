# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading
import platform
# third-party

# sjva 공용
from framework import db, scheduler, path_app_root, path_data
from framework.job import Job
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting
#########################################################


class Logic(object):
    db_default = { 
        'db_version' : '4',
        'rclone_info' : '', # rclone 
        'size_upload' : '0',
        'size_download' : '0',
        'rclone_path' : os.path.join(path_app_root, 'bin', platform.system(), 'rclone'),
        'rclone_config_path' : os.path.join(path_data, 'db', 'rclone.conf'),
        'defalut_remote_path' : '',

        'av_sub_last_updated_time' : '',
        'av_sub_show_poster' : 'False',
        'av_sub_folder_name' : '',
        'av_sub_plex_match_rule' : '',
        'last_list_option' : '',
        'user_copy_dest_list' : u'default = \nshare_movie,국내 = \nshare_movie,외국 = \nshare_ktv,드라마 = \nshare_ktv,예능 = \nshare_ktv,교양 = \nshare_ftv = \nshare_etc = ',
    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            Logic.migration()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            Logic.db_init()
            
            # 기능별로
            #if ModelSetting.get_bool('auto_start'):
            #    Logic.scheduler_start('download')
            #if ModelSetting.get_bool('subcat_use'):
            #    Logic.scheduler_start('subcat')

            # 편의를 위해 json 파일 생성
            from plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_start(sub):
        try:
            job_id = '%s_%s' % (package_name, sub)
            #if sub == 'download':
            #    job = Job(package_name, job_id, ModelSetting.get('interval'), Logic.scheduler_function, u"AV 파일처리", False, args=sub)
            #elif sub == 'subcat':
            #    job = Job(package_name, job_id, ModelSetting.get('subcat_interval'), Logic.scheduler_function, u"AV 자막다운로드", False, args=sub)
            #scheduler.add_job_instance(job)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_stop(sub):
        try:
            job_id = '%s_%s' % (package_name, sub)
            scheduler.remove_job(job_id)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_function(sub):
        #if sub == 'download':
        #    LogicDownload.scheduler_function()
        #elif sub == 'subcat':
        #    LogicSubcat.scheduler_function()
        pass


    @staticmethod
    def reset_db(sub):
        logger.debug('reset db:%s', sub)
        #if sub == 'download':
        #    return LogicDownload.reset_db()
        #elif sub == 'subcat':
        #    return LogicSubcat.reset_db()
        #return False


    @staticmethod
    def one_execute(sub):
        logger.debug('one_execute :%s', sub)
        try:
            job_id = '%s_%s' % (package_name, sub)
            if scheduler.is_include(job_id):
                if scheduler.is_running(job_id):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(job_id)
                    ret = 'scheduler'
            else:
                def func():
                    time.sleep(2)
                    Logic.scheduler_function(sub)
                threading.Thread(target=func, args=()).start()
                ret = 'thread'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret
    
          
    @staticmethod
    def process_telegram_data(data):
        try:
            logger.debug(data)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    

    @staticmethod
    def migration():
        try:
            if ModelSetting.get('db_version') == '1':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_av_sub_item ADD plex_json JSON' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '2')
                db.session.flush()
            if ModelSetting.get('db_version') == '2':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_av_sub_item ADD remote_path VARCHAR' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '3')
                db.session.flush()
            if ModelSetting.get('db_version') == '3':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_av_sub_item ADD status INT' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '4')
                db.session.flush()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    ##################################################################################

    

    
