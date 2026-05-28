import os
import json
import time

from selenium.webdriver.common.by import By
from tool.DeepSeekAsk import DeepSeekAsk
from tool.decode_secret import DecodeSecret

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def is_finished_test(driver):
    """
    检查章节测验是否已完成
    :param driver: Selenium WebDriver
    :return: True=已完成, False=未完成
    """
    try:
        driver.find_element(By.CLASS_NAME, 'testTit_status_complete')
        print('测验已完成', flush=True)
        return True
    except Exception:
        return False


def get_answer(api, question_content, type):
    """
    调用 DeepSeek 获取题目答案
    :param api: API 密钥
    :param question_content: 题目内容（含选项）
    :param type: 题目类型
    :return: 答案列表
    """
    answer = []
    try:
        answer = DeepSeekAsk(api, question_content, type)
    except:
        print('获取答案失败',flush=True)
        pass
    return answer


def save_data(driver):
    """
    从考试页面提取所有题目的类型、题干、选项和可点击元素
    :param driver: Selenium WebDriver
    :return: (question_commit, questions_title, questions_options)
             question_commit: 每个题目的选项 DOM 元素列表
             questions_title: 每个题目的 "类型:题干" 字符串列表
             questions_options: 每个题目的 "选项字母:选项内容" 字符串列表
    """
    question_commit = []
    questions_title = []
    questions_options = []

    # 切换到测验的 iframe 层级：default → 测验 iframe → frame_content
    quize_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="/modules/work/index.html"]')
    driver.switch_to.frame(quize_iframe)
    driver.switch_to.frame('frame_content')

    # 如果测验已提交完成，直接返回空数据
    if is_finished_test(driver):
        return [], [], []

    # 初始化字体解密器，自动检测是否需要解密
    decoder = DecodeSecret(status_code=2)
    decoder.get_font_face(driver)

    # 遍历页面中的每个题目容器（singleQuesId）
    question_contents = driver.find_elements(By.CLASS_NAME, 'singleQuesId')
    for question_content in question_contents:
        element_parent = question_content.find_element(By.XPATH, '..')
        parent_id = element_parent.get_attribute('id')
        # 只处理父容器 id 包含 "ZyBottom" 的题目（过滤掉标题等非题目元素）
        if 'ZyBottom' not in parent_id:
            continue

        # 读取并解密题目的完整文本内容
        inner = decoder.decode(question_content.get_attribute('innerText'))
        lines = [l.strip() for l in inner.split('\n') if l.strip()]
        # lines 预期格式: [题号, 【题型标签】, 题干文字, A, 选项A内容, B, 选项B内容, ...]
        if len(lines) < 4:
            continue

        type_text = lines[1]

        # 根据题型标签提取题型名称
        if '单选题' in type_text:
            title = '单选题'
            title_content = lines[2]
        elif '判断题' in type_text:
            title = '判断题'
            title_content = lines[2]
        elif '多选题' in type_text:
            title = '多选题'
            title_content = lines[2]
        else:
            print(f'未知题目类型: {type_text}', flush=True)
            continue

        # 存储 "类型:题干" 格式的题目信息
        questions_title.append(title + ':' + title_content)

        # 从第4行开始解析选项（A, 选项A, B, 选项B, ...）
        opts = []
        opt_index = 3
        while opt_index + 1 < len(lines):
            opt_letter = lines[opt_index]
            if opt_letter in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
                opt_content = lines[opt_index + 1]
                opts.append(opt_letter + ':' + opt_content)
                opt_index += 2
            else:
                opt_index += 1
        questions_options.append(opts)

    # 全页收集所有可点击的选项元素，按每道题的选项数量逐一切分
    all_single_els = driver.find_elements(By.CSS_SELECTOR, 'li[onclick*="addChoice(this)"]')
    all_multi_els = driver.find_elements(By.CSS_SELECTOR, 'li[onclick*="addMultipleChoice(this)"]')
    single_idx = 0
    multi_idx = 0
    for i, opts in enumerate(questions_options):
        title_text = questions_title[i]
        n = len(opts)
        if '多选题' in title_text:
            question_commit.append(all_multi_els[multi_idx:multi_idx + n])
            multi_idx += n
        else:
            question_commit.append(all_single_els[single_idx:single_idx + n])
            single_idx += n

    return question_commit, questions_title, questions_options


def finished_test_target(driver):
    """
    完成当前章节测验：获取答案 → 自动勾选 → 提交
    :param driver: Selenium WebDriver
    """
    # 从页面提取题目数据
    question_commit, questions_title, questions_options = save_data(driver)

    # 如果测验已完成或没有题目，直接退出
    if not questions_title:
        return

    with open(os.path.join(BASE_DIR, 'account_info.json'), 'r', encoding='utf-8') as f:
        account_info = json.load(f)
    api = account_info['deepseek_API_KEY']

    # 逐题调用 API 获取答案
    question_num = 0
    for question_title, question_options in zip(questions_title, questions_options):
        # 从 "类型:题干" 中拆出题型
        question_type = question_title.split(':')[0]
        # 构造发给 DeepSeek 的完整内容：题干 + 所有选项
        question_with_options = question_title
        for option in question_options:
            question_with_options += '\n' + option

        # 获取答案
        answer = get_answer(api, question_with_options, question_type)
        if type(answer) == str:
            answer = eval(answer)
        if not answer:
            print('获取答案失败', flush=True)
            question_num += 1
            continue

        # 将答案字母（["A","B"]）转换为选项索引（[0,1]）
        answer_num = []
        options = [option[0] for option in question_options]
        for ans in answer:
            if ans in options:
                answer_num.append(options.index(ans))
        answer_num = list(set(answer_num))

        # 滚动到选项位置并点击
        for i in answer_num:
            option_el = question_commit[question_num][i]
            driver.execute_script('arguments[0].scrollIntoView({behavior: "smooth", block: "center"});', option_el)
            time.sleep(0.3)
            driver.execute_script(f'arguments[0].click();', option_el)
            time.sleep(0.5)
        question_num += 1

    # 点击提交按钮
    time.sleep(1)
    submit_button = driver.find_element(By.CSS_SELECTOR, 'a[onclick="btnBlueSubmit();"]')
    driver.execute_script(f'arguments[0].click();', submit_button)
    time.sleep(1)

    # 切换回默认内容，点击确认提交弹窗
    driver.switch_to.default_content()
    try:
        element = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="确定"]')
        driver.execute_script(f'arguments[0].click();', element)
    except:
        print('提交失败', flush=True)
    time.sleep(2)

    # 切回主 iframe，方便后续操作
    driver.switch_to.frame('iframe')
