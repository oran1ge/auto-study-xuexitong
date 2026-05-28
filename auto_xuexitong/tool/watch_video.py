import os
from tool.DeepSeekAsk import DeepSeekAsk
import json
from selenium.webdriver.common.by import By
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_answer(question_title, question_type):
    """
    从配置文件读取 API 密钥，调用 DeepSeek 获取答案
    :param question_title: 题目内容（含选项）
    :param question_type: 题目类型
    :return: 答案列表
    """
    answer = []
    with open(os.path.join(BASE_DIR, 'account_info.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        api = data['deepseek_API_KEY']
    try:
        answer = DeepSeekAsk(api, question_title, question_type)
    except:
        print('获取答案失败', flush=True)
        pass
    return answer

def finish_video_question(element, driver):
    """
    处理视频中弹出的题目（单选题、判断题、多选题）
    :param element: 题目容器 DOM 元素
    """
    try:
        # 提取题目文字
        question_title = element.find_element(By.CLASS_NAME, 'tkItem_title').text
        # 提取题目类型
        try:
            question_type=element.find_element(By.CLASS_NAME,'tkTopic_type').text
        except:
            question_type=element.find_element(By.CLASS_NAME,'tkTopic_title').text
        # 提取所有选项
        options = element.find_element(By.CLASS_NAME, 'tkItem_ul')
        options = options.find_elements(By.TAG_NAME, 'li')
        options_txt=[option.text for option in options]
        submit = element.find_element(By.ID, 'videoquiz-submit')
        # 调用 DeepSeek 获取答案
        answer = get_answer(question_title + '\n' + str(options_txt), question_type)
        if type(answer) == str:
            answer = eval(answer)
        if not answer:
            print(f'~~~获取答案失败，题目：{question_title}', flush=True)
            return
        # 将答案选项字母（A/B/C/D）转换为对应的索引位置
        answer_num = []
        option_num = 0
        if question_type == '单选题' or question_type == '判断题':
            for option in options_txt:
               if answer[0] in option:
                    break
               option_num += 1
            answer_num.append(option_num)
        elif question_type == '多选题':
            if len(answer) == 1:
                lst = answer[0]
            else:
                lst = answer
            for option in options_txt:
                for ans in lst:
                    if ans in option:
                        answer_num.append(option_num)
                option_num += 1
            answer_num = list(set(answer_num))
        # 点击正确答案对应的选项
        for ans in answer_num:
            checked=options[ans].find_elements(By.CSS_SELECTOR,'[checked="checked"]')
            if not checked:
                options[ans].click()
                time.sleep(1)
            else:
                print(f'•已选择选项{ans}', flush=True)
                continue
        # 点击提交按钮
        submit.click()
        time.sleep(1)
        print('~~~已提交答案~~~', flush=True)
        # 点击"返回视频"按钮，关闭答题弹窗
        try:
            return_video = driver.find_element(By.CSS_SELECTOR, '[class="bntWhiteBorder ans-videoquiz-back fr"]')
            return_video.click()
            time.sleep(1)
        except Exception:
            pass
        # 点击"继续学习"按钮，恢复视频播放
        try:
            continue_learn = element.find_element(By.ID, 'videoquiz-continue')
            continue_learn.click()
            time.sleep(1)
        except Exception:
            pass
        return
    except Exception:
        print('~~~`提交答案失败~~~', flush=True)
        return

def is_finished(driver, video_iframe, pre_time='0:00'):
    """
    判断视频是否播放完成
    :param driver: Selenium WebDriver
    :param video_iframe: 视频所在的 iframe 元素
    :param pre_time: 上一次记录的视频播放进度
    :return: True=已完成, False=未完成
    """
    # 切换到视频 iframe 中读取播放时间
    driver.switch_to.frame(video_iframe)
    try:
        current_el = driver.find_element(By.CLASS_NAME, 'vjs-current-time-display')
        current_time = current_el.get_attribute('textContent') or current_el.text
        total_el = driver.find_element(By.CLASS_NAME, 'vjs-duration-display')
        total_time = total_el.get_attribute('textContent') or total_el.text
        # 当前时间等于总时长 → 播放完成
        if current_time == total_time:
            return True
        # 当前时间没变化 → 可能暂停了，尝试重新播放
        if current_time == pre_time:
            print('~~~视频意外暂停，当前时间未改变~~~', flush=True)
            time.sleep(1)
            element = driver.find_element(By.CLASS_NAME, 'vjs-big-play-button')
            driver.execute_script("arguments[0].click();", element)
            print('~~~已点击播放按钮~~~', flush=True)
            time.sleep(1)
            current_el = driver.find_element(By.CLASS_NAME, 'vjs-current-time-display')
            current_time = current_el.get_attribute('textContent') or current_el.text
            if current_time != pre_time:
                print('~~~视频播放继续~~~', flush=True)
            else:
                print('~~~视频播放继续失败,可能弹出弹窗~~~', flush=True)
            return False
    except Exception:
        print('~~~获取视频时长失败~~~', flush=True)
        return False
    return False

def watch_video(driver, video_iframe, i):
    """
    播放指定索引的视频
    :param driver: Selenium WebDriver
    :param video_iframe: 视频 iframe 元素
    :param i: 视频序号（用于日志输出）
    """
    # 滚动到视频位置
    driver.execute_script("arguments[0].scrollIntoView();", video_iframe)
    driver.switch_to.frame(video_iframe)
    # 关闭笔记弹窗（如果存在）
    try:
        element = driver.find_element(By.CLASS_NAME, 'writeNote_vid_blue')
        driver.execute_script("arguments[0].click();", element)
        print('<已关闭笔记弹窗>', flush=True)
    except Exception:
        pass
    # 点击播放按钮
    element = driver.find_element(By.CLASS_NAME, 'vjs-big-play-button')
    driver.execute_script("arguments[0].click();", element)
    time.sleep(1)
    # 静音
    try:
        element = driver.find_element(By.CLASS_NAME, 'vjs-mute-control')
        driver.execute_script("arguments[0].click();", element)
        print('<已静音>', flush=True)
    except Exception:
        pass
    # 获取视频总时长
    time.sleep(2)
    element = driver.find_element(By.CLASS_NAME, 'vjs-duration-display')
    total_time = element.text
    print(f'•第{i + 1}个视频总时长: {total_time}，即将播放视频，期间不要操作其他页面，否则会导致视频播放异常>>>', flush=True)
    pre_time = '0:00'
    # 切回到外层 iframe
    driver.switch_to.parent_frame()
    while True:
        time.sleep(2)
        # 检测并关闭网络异常弹窗
        try:
            driver.switch_to.frame(video_iframe)
            internet_choice = driver.find_element(By.CSS_SELECTOR, "[class='ans-vjserrdisplay-opts']")
            choice_list = internet_choice.find_elements(By.CSS_SELECTOR, "[name='ans-vjserrdisplay-opt']")
            for choice in choice_list:
                choice.click()
                time.sleep(0.5)
            print('已关闭网络异常弹窗', flush=True)
            driver.switch_to.parent_frame()
        except Exception:
            driver.switch_to.parent_frame()
            pass
        # 检测视频中是否弹出题目
        try:
            driver.switch_to.frame(video_iframe)
            time.sleep(1)
            element = driver.find_element(By.CLASS_NAME, 'tkTopic')
            print('~~~视频中弹出题目，正在解决问题~~~', flush=True)
            finish_video_question(element, driver)
        except Exception:
            pass
        finally:
            driver.switch_to.parent_frame()
            time.sleep(1)
        # 检测视频是否播放完成
        if is_finished(driver, video_iframe, pre_time):
            print(f'•第{i + 1}个视频播放完成>>>', flush=True)
            break
        # 记录当前播放进度，用于下次比较
        current_el = driver.find_element(By.CLASS_NAME, 'vjs-current-time-display')
        pre_time = current_el.get_attribute('textContent') or current_el.text
        driver.switch_to.parent_frame()


def finished_video_target(driver, video_iframes):
    """
    完成页面中所有未完成的视频任务
    :param driver: Selenium WebDriver
    :param video_iframes: 视频 iframe 元素列表
    """
    time.sleep(0.5)
    n = len(video_iframes)
    print(f'<<<共 {n} 个视频>>>', flush=True)
    for i in range(n):
        video_iframe = video_iframes[i]
        # 确保在正确的 iframe 中
        driver.switch_to.default_content()
        try:
            driver.switch_to.frame('iframe')
        except Exception:
            pass
        time.sleep(1)
        # 检查该视频是否为"未完成"状态
        try:
            task_points = driver.find_elements(By.CSS_SELECTOR, '.ans-job-icon.ans-job-icon-clear')
            label = task_points[i].get_attribute('aria-label')
            if '任务点未完成' in label:
                print(f'•第{i + 1}个视频未播放完成，即将播放视频', flush=True)
                watch_video(driver, video_iframe, i)
            else:
                print(f'•第{i + 1}个视频已播放完成', flush=True)
        except Exception:
            pass
