import logging
import math
import os
import time

import api
import file
import request
from media import download_file, download_media


def get_folder_all_medias(fid: int, media_count: int, limiters: list[file.Limiter]) -> tuple[list, list]:
    """
    获取线上符合要求的所有投稿信息
    :param fid: 收藏夹id
    :param media_count: 投稿数量
    :param limiters: 筛选条件
    :return: 线上仍有效和已失效的投稿信息
    """

    page_count = math.ceil(media_count / 20)
    exists_medias = []
    deleted_medias = []
    for page_id in range(page_count):
        # B站系统限制，每次获取一页
        url = api.generate_fav_content_url(fid, page_id)
        resp = request.request_retry_json(url)
        if resp['code'] != 0:
            logging.error('get favorite folder error: ' + str(fid))
            continue
        medias = []
        for media in resp['data']['medias']:
            for limiter in limiters:
                if media['fav_time'] >= limiter.after and media['duration'] <= limiter.max_duration:
                    medias.append(media)
                    break
        exists_medias += [media for media in medias if media['title'] != '已失效视频']
        deleted_medias += [media for media in medias if media['title'] == '已失效视频']
        time.sleep(1)

    return exists_medias, deleted_medias


def get_media_all_pages(bv_id: str) -> list[dict]:
    url = api.generate_media_pages_url(bv_id)
    resp = request.request_retry_json(url)
    if resp['code'] == -404:
        logging.error('media all pages not find' + bv_id)
        return []
    elif resp['code'] != 0:
        logging.error('get media pages error: ' + bv_id)
        return []
    return [page for page in resp['data']]


def main():
    """
    执行更新备份
    :return: None
    """

    aims = file.read_aim_json()

    # 本地所有备份的bv号
    local_bv_id_set = file.read_local_json()
    # 已被删除备份的bv号
    deleted_bv_id_set = file.read_deleted_json()
    # 未及时备份被删投稿的残余信息和bv号
    lost_list = file.read_lost_json()
    lost_bv_id_set: set[str] = set([lost['bv_id'] for lost in lost_list])

    new_favorite_medias = []
    new_lost_medias = []
    new_favorite_medias_id = set[str]()
    new_deleted_medias_id = set[str]()
    new_lost_medias_id = set[str]()
    for aim in aims:
        exists_medias, deleted_medias = get_folder_all_medias(aim.fid, aim.media_count, aim.limiters)
        # 新收藏投稿信息（去重）：本地没有，线上可用
        new_favorite_medias += [media for media in exists_medias if
                                media['bv_id'] not in local_bv_id_set and
                                media['bv_id'] not in new_favorite_medias_id]
        # 新收藏投稿bv
        new_favorite_medias_id.update([media['bv_id'] for media in exists_medias if
                                       media['bv_id'] not in local_bv_id_set])

        # 已备份新删除投稿bv：本地有，线上不可用
        new_deleted_medias_id.update([media['bv_id'] for media in deleted_medias if
                                      media['bv_id'] in local_bv_id_set and
                                      media['bv_id'] not in deleted_bv_id_set])

        # 未备份新删除投稿残余信息
        new_lost_medias += [media for media in deleted_medias if
                            media['bv_id'] not in lost_bv_id_set and
                            media['bv_id'] not in new_lost_medias_id]
        # 未备份新删除投稿bv
        new_lost_medias_id.update([media['bv_id'] for media in deleted_medias if
                                   media['bv_id'] not in lost_bv_id_set])

    # 显示本次更新目标
    new_favorite_count = len(new_favorite_medias_id)
    new_deleted_count = len(new_deleted_medias_id)
    new_lost_count = len(new_lost_medias_id)
    logging.info('new favorite: %d new deleted: %d new lost: %d' %
                 (new_favorite_count, new_deleted_count, new_lost_count))

    # 读取已备份新删除投稿信息
    new_deleted_medias = [file.read_media_json(bv_id) for bv_id in new_deleted_medias_id]

    def output_media(media):
        logging.info('title: %s duration: %d' % (media['title'], media['duration']))

    if new_favorite_count != 0:
        logging.info('新收藏-----------')
        [output_media(media) for media in new_favorite_medias]
    if new_deleted_count != 0:
        logging.info('新删除-----------')
        [output_media(media) for media in new_deleted_medias]
    if new_lost_count != 0:
        logging.info('新丢失-----------')
        [output_media(media) for media in new_lost_medias]

    if new_favorite_count + new_deleted_count + new_lost_count == 0:
        logging.info('没有新收藏、新删除和新丢失！')
        return

    # 决定是否执行
    choose = input('是否执行更新？输入n不执行').strip().lower()
    if choose != '' and choose[0].lower() == 'n':
        return

    # 保存未备份已删除投稿残余信息
    file.write_lost_json(lost_list + new_lost_medias)

    for media in new_deleted_medias:
        # 链接已备份新删除投稿到单独文件夹
        file.create_link_from_all_to_deleted(media['bv_id'], media['page'])
        # 已删除文件夹创建投稿标题名字文件
        file.create_name_file(media['bv_id'], media['page'], media['title'],
                              [page['part'] for page in media['pages']])
        # 每次更新已备份已删除bv
        deleted_bv_id_set.add(media['bv_id'])
        file.write_deleted_json(list[str](deleted_bv_id_set))

    # 更新备份未删除投稿到本地
    for media in new_favorite_medias:
        pages: list[dict] = get_media_all_pages(media['bv_id'])
        bv_id = media['bv_id']
        # 下载封面图片
        download_file(bv_id, media['cover'], os.path.join(file.all_path, bv_id + '.jpg'))
        # 保存投稿信息
        file.write_json_file(os.path.join(file.all_path, bv_id + '.json'), media)
        # 下载所有分P
        cid_list: list[int] = [page['cid'] for page in pages]
        logging.info('cid_list: %s' % cid_list)
        for i in range(len(cid_list)):
            cid = cid_list[i]
            if i != 0:
                logging.info('sleep for 3s')
                time.sleep(3)

            page_id = str(i + 1)
            if len(cid_list) == 1:
                page_id = ''
            download_media(bv_id, cid, file.all_path, page_id)
        # 更新本地已备份投稿信息
        local_bv_id_set.add(bv_id)
        file.write_local_json(list[str](local_bv_id_set))
