import time

from selenium import webdriver
import json
from tool.chapter_test import finished_test_target
from tool.watch_video import finished_video_target
from selenium.common import NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options


def start_edge_driver():
    """启动 Edge 浏览器，返回 WebDriver 实例"""
    print('浏览器启动中...')
    options = Options()
    options.use_chromium = True
    return webdriver.Edge(options=options)


def turn_page(page_name, driver):
    """在浏览器所有标签页中查找并切换到指定标题的页面"""
    time.sleep(1)
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if page_name in driver.title:
            return True
    return False


def save_cookie_to_file(driver):
    """将当前浏览器 cookies 保存到 cookies.json 文件"""
    cookies = driver.get_cookies()
    with open('cookies.json', 'w') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=4)
    print('cookies已经保存到文件', flush=True)


def auto_login_with_cookie(driver, path='https://i.chaoxing.com/'):
    """
    尝试通过之前保存的 cookie 跳过登录
    :return: True=登录成功, False=需要重新登录
    """
    with open('cookies.json', 'r') as f:
        cookies = json.load(f)
    for cookie in cookies:
        try:
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
        except Exception as e:
            pass
    driver.refresh()
    time.sleep(2)
    driver.get(path)
    if driver.title == '用户登录':
        return False
    return True


def login_study(driver, path='https://i.chaoxing.com/'):
    """登录学习通：优先密码登录，失败则尝试 cookie 或扫码"""
    driver.get(path)
    print('进入登录页面', flush=True)

    # 从 account_info.json 读取账号密码
    with open('account_info.json', 'r', encoding='utf-8') as f:
        account_info = json.load(f)
    phone_number = account_info['phone_number']
    password = account_info['password']

    # 输入账号密码
    element1 = driver.find_element(By.CLASS_NAME, 'ipt-tel')
    element1.send_keys(phone_number)
    element2 = driver.find_element(By.CLASS_NAME, 'ipt-pwd')
    element2.send_keys(password)

    turn_page('用户登录', driver)

    # 点击登录按钮
    login_btn = driver.find_element(By.ID, 'loginBtn')
    login_btn.click()
    time.sleep(3)

    if driver.title == '用户登录':
        # 账号密码错误，尝试 cookie 登录
        print('账号密码错误，正在尝试跳过登录...', flush=True)
        if auto_login_with_cookie(driver):
            print('跳过登录成功', flush=True)
            return
    else:
        print('账号密码登录成功', flush=True)
        save_cookie_to_file(driver)
        return

    # 最后尝试扫码登录
    print('跳过登录失败，请通过扫描二维码登录...', flush=True)
    while True:
        if driver.title != '用户登录':
            break
        time.sleep(1)
    print('验证码登录成功')
    return


def save_course_to_file(driver):
    """将当前用户的所有课程名称保存到 courses.json"""
    driver.switch_to.frame('frame_content')
    elements = driver.find_elements(By.CLASS_NAME, 'course-name')
    courses = [el.text for el in elements]
    with open('courses.json', 'w', encoding='utf-8') as f:
        json.dump(courses, f, ensure_ascii=False, indent=4)
    print('课程保存成功', flush=True)


def into_course(course_name, driver):
    """
    从课程列表中找到指定课程并进入
    :param course_name: 课程名称
    """
    with open('courses.json', 'r', encoding='utf-8') as f:
        course_list = json.load(f)

    if course_name in course_list:
        elements = driver.find_elements(By.CLASS_NAME, 'course-name')
        for element in elements:
            if course_name in element.text:
                element.click()
                time.sleep(1)
                turn_page(course_name, driver)
                time.sleep(1)
                # 点击"开始学习"按钮（如果存在）
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, '.start-study.readclosecoursepop')
                    print('检测到开始学习按钮...', flush=True)
                    driver.execute_script("arguments[0].click();", btn)
                    print('已点击开始学习按钮', flush=True)
                except Exception:
                    pass
                break
        time.sleep(2)
        print('进入课程成功', flush=True)
    else:
        print('未找到课程，请确认课程名称正确', flush=True)


def find_target(driver, target='章节'):
    """
    进入课程后定位到指定章节的第一个未完成任务点
    :param target: 导航标签名称，一般为"章节"
    """
    time.sleep(1)
    # 点击"章节"标签
    try:
        element = driver.find_element(By.XPATH, f'//a[@title="{target}"]')
        element.click()
    except Exception:
        pass

    # 切换到章节内容的 iframe
    driver.switch_to.frame('frame_content-zj')
    time.sleep(0.5)

    # 找到所有任务列表项，跳过已完成的，点击第一个未完成的任务
    elements = driver.find_elements(By.CLASS_NAME, 'catalog_task')
    if len(elements) == 0:
        print('该章节没有任务点...')
        return
    else:
        for element in elements:
            if '已完成' in element.get_attribute('textContent'):
                continue
            else:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(1)
                print('进入第一个未完成任务点', flush=True)
                break


def skip_reminer(driver):
    """
    跳过"任务点完成"提示弹窗，点击"下一节"按钮
    """
    try:
        driver.find_element(By.ID, 'jobFinishTipFocus')
        driver.find_element(By.CLASS_NAME, 'nextChapter').click()
        time.sleep(1)
    except Exception:
        time.sleep(1)
        pass


def reco_page_message(driver):
    """
    识别当前页面包含哪些类型的任务点（视频、测验）
    :return: dict, 如 {"视频": [iframe列表]} 或 {"测验": element}
    """
    # 先切回默认内容
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    # 点击"展开"按钮（如果存在），展开所有任务列表
    try:
        btn = driver.find_element(By.CLASS_NAME, 'switchbtn')
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except Exception:
        pass

    # 切换到主 iframe
    driver.switch_to.frame('iframe')
    target_dit = {}
    time.sleep(1)

    # 检测是否存在视频任务点
    try:
        video_iframes = driver.find_elements(By.CSS_SELECTOR, '.ans-attach-online.ans-insertvideo-online')
        n = len(video_iframes)
        if n == 0:
            print('<<该章节没有视频任务点>>', flush=True)
        else:
            print(f'<<检测到{n}个视频任务点>>', flush=True)
            target_dit['视频'] = video_iframes
    except Exception:
        pass

    # 检测是否存在章节测验
    try:
        quize_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="/modules/work/index.html"]')
        driver.switch_to.frame(quize_iframe)
        driver.switch_to.frame('frame_content')
        element = driver.find_element(By.CLASS_NAME, 'newTestTitle')
        element1 = element.find_element(By.CSS_SELECTOR, 'div[class="fl TestTitle_name"]')
        text = element1.get_attribute('textContent') or element1.text
        if '章节测验' in text:
            print('<<检测到章节测验>>', flush=True)
            target_dit['测验'] = element
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
    except Exception:
        print('<<该章节没有作业任务点>>', flush=True)
    finally:
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')

    if len(target_dit) == 0:
        print('页面内容识别失败...', flush=True)
    return target_dit



def turn_next_page(driver):
    """
    切换到当前章节的下一个任务点
    :return: True=切换成功, False=没有下一个任务点
    """
    # 切回顶层页面，查找"下一页"按钮
    driver.switch_to.default_content()
    try:
        element = driver.find_element(By.ID, 'prevNextFocusNext')
        state = element.get_attribute('style')
        # 如果按钮被隐藏（display: none），说明没有下一页
        if "display: none" in state:
            time.sleep(1)
            driver.switch_to.frame('iframe')
            return False
        element.click()
        # 跳过弹窗
        skip_reminer(driver)
        print('切换到下一个任务点', flush=True)
        print('---------------------', flush=True)
        time.sleep(1)
        # 重新展开任务列表
        try:
            btn = driver.find_element(By.CLASS_NAME, 'switchbtn')
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except Exception:
            pass
        driver.switch_to.frame('iframe')
        return True
    except Exception as e:
        time.sleep(1)
        driver.switch_to.frame('iframe')
        return False


def finish_one_page_target(driver):
    """
    完成当前页面的所有任务点（视频/测验）
    根据 reco_page_message 返回的结果，调用对应的处理函数
    """
    page_message = reco_page_message(driver)
    if '视频' in page_message.keys():
        finished_video_target(driver, page_message['视频'])
    elif '测验' in page_message.keys():
        finished_test_target(driver)
    else:
        print('识别页面内容失败，自动跳到下一节', flush=True)


def run(course_name):
    """
    主流程：启动浏览器 → 登录 → 进课程 → 循环完成所有任务点
    :param course_name: 要完成的课程名称
    """
    driver = start_edge_driver()
    login_study(driver)
    save_course_to_file(driver)
    into_course(course_name, driver)
    find_target(driver)

    # 不断完成当前页任务 → 翻到下一页，直到没有下一页
    while True:
        finish_one_page_target(driver)
        if not turn_next_page(driver):
            break


if __name__ == '__main__':
    """
    该脚本由 小小橘Orange 编写
    用于自动学习 章节 中的视频观看和作业
    注意：该脚本需要在 Edge 浏览器中运行
    请在 account_info.json 中填写自己的手机号,密码,deepseek_API_KEY
    后续会不间断更新该脚本
    """
    try:
        run('大学美育')
    except NoSuchWindowException as e:
        print('窗口意外关闭', flush=True)
