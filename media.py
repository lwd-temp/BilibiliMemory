import logging
import os
import file
import request

import api


def download_file_url_list(bv_id: str, url_list: list[str], file_path: str):
    fake_referer_url = 'https://www.bilibili.com/video/' + bv_id
    resp = request.request_retry_url_list(url_list, headers={
        'referer': fake_referer_url,
        'range': 'bytes=0-'})
    with open(file_path, 'wb') as f:
        f.write(resp.content)


def download_file(bv_id: str, url: str, file_path: str):
    fake_referer_url = 'https://www.bilibili.com/video/' + bv_id
    resp = request.request_retry(url, headers={
        'referer': fake_referer_url,
        'range': 'bytes=0-'})
    with open(file_path, 'wb') as f:
        f.write(resp.content)


def merge_media(audio_file_path: str, video_file_path: str, file_path: str):
    rst = os.system(
        'ffmpeg-n5.0-latest-win64-lgpl-shared-5.0\\bin\\ffmpeg -i %s -i %s'
        ' -c:v copy -c:a aac -strict experimental %s' % (video_file_path, audio_file_path, file_path))
    if rst != 0:
        raise 'ffmpeg error'
    os.remove(audio_file_path)
    os.remove(video_file_path)


def download_media(bv_id: str, first_cid: int, media_path: str, page_id: str):
    audio_url_list, video_url_list = api.generate_media_audio_video_url(bv_id, first_cid)
    # 下载音频
    audio_file_path = os.path.join(file.tmp_path, 'tmp_audio.m4s')
    logging.info('download audio ' + bv_id + ' ' + str(first_cid) + ':')
    download_file_url_list(bv_id, audio_url_list, audio_file_path)
    logging.info('download audio ' + bv_id + ' ' + str(first_cid) + ' finished.')
    # 下载视频
    video_file_path = os.path.join(file.tmp_path, 'tmp_video.m4s')
    logging.info('download video ' + bv_id + ' ' + str(first_cid) + ':')
    download_file_url_list(bv_id, video_url_list, video_file_path)
    logging.info('download video ' + bv_id + ' ' + str(first_cid) + ' finished.')
    # 合并音视频后删除临时文件
    if page_id != '':
        file_path = os.path.join(media_path, bv_id + '_' + page_id + '.mp4')
    else:
        file_path = os.path.join(media_path, bv_id + '.mp4')
    logging.info('merge media ' + bv_id + ' ' + str(first_cid))
    merge_media(audio_file_path, video_file_path, file_path)
