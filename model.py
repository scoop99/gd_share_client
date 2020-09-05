# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime,timedelta
import json
import os
import re

# third-party
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref
from sqlalchemy.orm.attributes import flag_modified
# sjva 공용
from framework import app, db, path_app_root
from framework.util import Util

# 패키지
from .plugin import logger, package_name

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))
#########################################################

from framework.common.plugin import get_model_setting
ModelSetting = get_model_setting(package_name, logger)


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
            