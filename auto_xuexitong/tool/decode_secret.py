import base64
import hashlib
import json
import os
import re
import unicodedata
from xml.dom.minidom import parse

from fontTools.ttLib import TTFont


class DecodeSecret:
    """解析学习通字体加密字符串。

    学习通通过自定义字体将 DOM 中的文字替换为乱码字符（如 "嘓嘑嘒"），
    再利用 CSS @font-face 将乱码映射回正确显示。此类从页面的字体文件
    中提取映射关系，将乱码还原为真实文字。

    status_code 取三种值：
        0 - 不启用解密
        1 - 启用解密
        2 - 自动判断是否解密（推荐）
    """

    def __init__(self, status_code=2):
        if status_code not in (0, 1, 2):
            raise ValueError(
                f'status_code 取值必须为 0、1、2，当前为 {status_code}'
            )
        self._status_code = status_code

        # font_dict.txt 放在项目根目录
        self._font_dict_path = os.path.join(os.path.dirname(__file__), '..', 'font_dict.txt')

        # _secret_dict: 页面字体中字形MD5 → Unicode码点（需要从当前页面提取）
        self._secret_dict = {}
        # _font_dict: 字体MD5 → 正确Unicode码点（来自预置的 font_dict.txt）
        self._font_dict = {}
        self._load_font_dict()

    def get_font_face(self, driver):
        """从页面 head 中提取 @font-face 的 base64 字体数据。"""
        if self._status_code == 0:
            return

        # 在页面 <head> 中查找所有 <style type="text/css"> 标签
        style_tags = driver.find_element(
            'tag name', 'head'
        ).find_elements('css selector', '[type="text/css"]')

        font_face_str = ''
        for tag in style_tags:
            inner = tag.get_attribute('innerHTML')
            if not inner:
                continue
            try:
                # 用正则提取 @font-face 中 src: url(data:font/ttf;base64,xxxxx) 的 base64 数据
                match = re.findall(r";base64,(.*)'[)]\s*format", inner)
                if match:
                    font_face_str = match[0]
                    break
            except Exception as e:
                print(f'当前 fontFace 无法解析：{e}', flush=True)
                continue

        if self._status_code == 1:
            if not font_face_str:
                print('英语题，无法解密', flush=True)
                return
        elif self._status_code == 2:
            # 自动模式：能找到字体就解密，找不到就不解
            if not font_face_str:
                self._status_code = 0
                return
            else:
                self._status_code = 1

        # 解析 base64 字体文件，提取字形映射
        self._build_secret_dict(font_face_str)

    def _build_secret_dict(self, font_face):
        """将 base64 字体数据解析为字形 MD5 到 Unicode 码点的映射。"""
        ttf_path = '.temp.ttf'
        xml_path = '.temp.xml'

        # 将 base64 解码为 .ttf 字体文件
        raw = base64.b64decode(font_face)
        with open(ttf_path, 'wb') as f:
            f.write(raw)

        # 用 fontTools 将 .ttf 解析为 .xml 格式
        font = TTFont(ttf_path)
        font.saveXML(xml_path)

        # 遍历 XML 中每个字形 (TTGlyph)
        dom = parse(xml_path)
        root = dom.documentElement
        for ttglyph in root.getElementsByTagName('TTGlyph'):
            name = ttglyph.getAttribute('name')
            if name == '.notdef':
                continue
            # 从字形名称（如 "uni4E2D"）中提取 Unicode 码点
            code = int(re.findall(r'uni(.*)', name)[0], 16)
            # 将字形的轮廓数据拼接后取 MD5，作为字形唯一标识
            glyph_xml = ''
            for contour in ttglyph.getElementsByTagName('contour'):
                glyph_xml += contour.toxml()
            md5 = hashlib.md5(glyph_xml.encode('utf-8')).hexdigest()
            # 存储映射：码点 → MD5
            self._secret_dict[code] = md5

        # 清理临时文件
        os.remove(ttf_path)
        os.remove(xml_path)

    def _load_font_dict(self):
        """加载字形 MD5 → 正确 Unicode 码点的映射表。

        此文件需要预先通过标准字体生成，包含大量常见字的映射。
        """
        if self._status_code == 0:
            return
        try:
            with open(self._font_dict_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # raw 格式: {"字形MD5值": 正确Unicode码点十进制值, ...}
            self._font_dict = {k: int(v) for k, v in raw.items()}
        except FileNotFoundError:
            print(f'font_dict.txt 不存在，路径：{self._font_dict_path}', flush=True)

    def decode(self, string):
        """解密被字体加密的字符串。

        流程：对每个字符的 Unicode 码点，先查 _secret_dict 得到字形 MD5，
        再查 _font_dict 得到正确的 Unicode 码点，最后转换为正确字符。
        """
        if self._status_code == 0:
            return string

        result = []
        for ch in string:
            # 获取当前字符 (乱码) 的字形 MD5
            md5 = self._secret_dict.get(ord(ch))
            if md5 is None:
                # 不在加密字体内，直接保留
                result.append(ch)
                continue
            # 通过 MD5 反查正确字符的码点
            true_code = self._font_dict.get(md5)
            if true_code is None:
                result.append(ch)
            else:
                # 将码点转换为字符，并用 NFKC 标准化
                result.append(unicodedata.normalize('NFKC', chr(true_code)))
        return ''.join(result)
