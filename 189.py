import base64
import hashlib
import json
import os
import re
import requests
import rsa
import sys

session = requests.session()
session.headers.update({
    'Referer': 'https://open.e.189.cn/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36'
})

RSA_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDY7mpaUysvgQkbp0iIn2ezoUyh
i1zPFn0HCXloLFWT7uoNkqtrphpQ/63LEcPz1VYzmDuDIf3iGxQKzeoHTiVMSmW6
FlhDeqVOG094hFJvZeK4OzA6HVwzwnEW5vIZ7d+u61RV1bsFxmB68+8JXs3ycGcE
4anY+YzZJcyOcEGKVQIDAQAB
-----END PUBLIC KEY-----
"""


# 加密密码
def encrypt(password: str) -> str:
    return base64.b64encode(
        rsa.encrypt(
            (password).encode('utf-8'),
            rsa.PublicKey.load_pkcs1_openssl_pem(RSA_KEY.encode())
        )
    ).decode()


b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")


def int2char(a):
    return BI_RM[a]


def b64tohex(a):
    d = ""
    e = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = b64map.index(list(a)[i])
            if 0 == e:
                e = 1
                d += int2char(v >> 2)
                c = 3 & v
            elif 1 == e:
                e = 2
                d += int2char(c << 2 | v >> 4)
                c = 15 & v
            elif 2 == e:
                e = 3
                d += int2char(c)
                d += int2char(v >> 2)
                c = 3 & v
            else:
                e = 0
                d += int2char(c << 2 | v >> 4)
                d += int2char(15 & v)
    if e == 1:
        d += int2char(c << 2)
    return d


def redirect():
    r = session.get("https://cloud.189.cn/udb/udb_login.jsp?pageId=1&redirectURL=/main.action")
    captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
    lt = re.findall(r'lt = "(.+?)"', r.text)[0]
    returnUrl = re.findall(r"returnUrl = '(.+?)'", r.text)[0]
    paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
    session.headers.update({"lt": lt})
    return captchaToken, returnUrl, paramId


def md5(s):
    hl = hashlib.md5()
    hl.update(s.encode(encoding='utf-8'))
    return hl.hexdigest()


# 验证码登陆（有密码可忽略不计）
def needcaptcha(captchaToken):
    r = session.post(
        url="https://open.e.189.cn/api/logbox/oauth2/needcaptcha.do",
        data={
            "accountType": "01",
            "userName": "{RSA}" + b64tohex(encrypt(username)),
            "appKey": "cloud"
        }
    )
    if r.text == "0":
        print("DONT NEED CAPTCHA")
        return ""
    else:
        print("NEED CAPTCHA")
        r = session.get(
            url="https://open.e.189.cn/api/logbox/oauth2/picCaptcha.do",
            params={"token": captchaToken}
        )
        with open("./captcha.png", "wb") as f:
            f.write(r.content)
            f.close()
        return input("验证码下载完成，打开 ./captcha.png 查看: ")


def save_cookie(username: str):
    with open(f"./{username}.cookie", mode="w") as f:
        json.dump(session.cookies.get_dict(), f, indent=2)
        f.close()


def load_cookie(username: str):
    cookie_file = f"./{username}.cookie"
    if os.path.exists(cookie_file):
        with open(cookie_file, mode="r") as f:
            cookie_dict = json.loads(f.read())
            f.close()
        [session.cookies.set(k, v, domain=".cloud.189.cn") for k, v in cookie_dict.items()]
        r = session.get("https://cloud.189.cn/v2/getUserLevelInfo.action")
        if "InvalidSessionKey" not in r.text: return True
    return False


def login():
    if load_cookie(username):
        return
    captchaToken, returnUrl, paramId = redirect()
    validateCode = needcaptcha(captchaToken)
    r = session.post(
        url="https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
        data={
            "appKey": "cloud",
            "accountType": '01',
            "userName": "{RSA}" + b64tohex(encrypt(username)),
            "password": "{RSA}" + b64tohex(encrypt(password)),
            "validateCode": validateCode,
            "captchaToken": captchaToken,
            "returnUrl": returnUrl,
            "mailSuffix": "@189.cn",
            "paramId": paramId
        }
    )
    msg = r.json()["msg"]
    if "登录成功" == msg:
        session.get(r.json()["toUrl"])
        save_cookie(username)
    else:
        print(msg)
        print('登陆失败！')
        exit(0)


# 简化使用流程，函数封装到一起
class TC_py:

    # 上传文件或者文件夹，参数1为上传文件路径，参数2为云盘中上传位置，可为相对路径比如：'我的云盘/我的天翼云盘/圣安地列斯.zip'，也可以为为绝对路径，比如file_id，
    @staticmethod
    def upload(file_or_folder_path, upload_path):
        if os.path.isfile(file_or_folder_path):
            try:
                int(upload_path)
                upload_file(file_or_folder_path, upload_path)
            except Exception as e:
                upload_file(file_or_folder_path, file_name2file_id(upload_path))
        else:
            try:
                int(upload_path)
                upload_folder(file_or_folder_path, upload_path)
            except Exception as e:
                upload_folder(file_or_folder_path, file_name2file_id(upload_path))

    # 下载文件夹或者文件，参数一为名字，参数二为文件在云盘中位置可为相对路径比如：'我的云盘/我的天翼云盘/圣安地列斯.zip', 参数三为下载路径，默认为当前文件夹，可以自行修改。
    @staticmethod
    def download(file_or_folder_path, download_path='./'):
        print('当前下载路径为：' + download_path)
        t = file_or_folder_path.split('/')
        if '.' not in t[-1]:
            download_folder(t[-1], file_name2file_id(file_or_folder_path), download_path)
        else:
            download_file(file_name2file_id(file_or_folder_path), download_path)

    # 删除文件夹格式为：我的云盘/我的图片/iPhone相册
    # 删除文件夹时，若文件夹不存在，则会删除上级目录，慎用
    # 删除文件格式为：我的云盘/我的图片/iPhone相册/IMG_0452_20200224152538.png
    # 默认移到垃圾箱，请自行登陆网页版删除
    @staticmethod
    def delete(file_or_folder_path):
        t = file_or_folder_path.split('/')
        t_parent = file_or_folder_path.replace('/' + t[-1], '')
        if '.' not in t[-1]:
            fileNam = t[-1]
            fileId = file_name2file_id(file_or_folder_path)
            isFolder = 1
            srcParentId = file_name2file_id(t_parent)
            # print(fileNam, fileId, isFolder, srcParentId)
        else:
            fileNam = t[-1]
            fileId = file_name2file_id(file_or_folder_path)
            isFolder = 0
            srcParentId = file_name2file_id(t_parent)
            # print(fileNam, fileId, isFolder, srcParentId)
        delete_folder(fileId, fileNam, isFolder, srcParentId)

    # 打印目录
    @staticmethod
    def list(folder_name):
        print(folder_name)
        get_list(file_name2file_id(folder_name))

    # 使用帮助
    @staticmethod
    def help():
        print('首次使用请设置的的账号和密码')
        print('根目录必须为：我的天翼云盘')
        print("显示我的云盘目录——>list 我的天翼云盘/我的照片")
        print("创建目录——>creat 我的天翼云盘/我的照片/iPhone")
        print("删除目录——>delete 我的天翼云盘/我的照片/iPhone")
        print("上传文件或者文件夹——>upload 文件本地路径 云盘路径")
        print("下载文件或者文件夹——>download 云盘中位置 本地路径（默认为当前程序路径）")
        print('退出程序——>quit')
        print('友情提示 1：创建目录只能创建单层，比如要去创建新的目' + '\n' + '录我的天翼云盘/a/b，要先创建a，再创建b目录 ')
        print('友情提示 2：删除目录一定要慎重，比如想要删除我的天翼' + '\n' + '云盘/a/b，如果b不存在，会直接删除a目录 ')
        print('友情提示 3：抓取的网页上传链接不支持断点上传，所以你' + '\n' + '上文文件大小取决于机器可用内存大小，比如1G可用' + '\n' + '内存的小鸡单次最高只能上传1G大小的文件，当然' + '\n' + '上传一堆小文件还是没问题的')

    # 创建文件夹
    @staticmethod
    def creat(folder_path):
        t = folder_path.split('/')
        t_parent = folder_path.replace('/' + t[-1], '')
        fileId = file_name2file_id(t_parent)
        creat_folder(t[-1], fileId)


# 计算文件大小
def get_file_size_str(filesize: int) -> str:
    if 0 < filesize < 1024 ** 2:
        return f"{round(filesize / 1024, 2)}KB"
    elif 1024 ** 2 < filesize < 1024 ** 3:
        return f"{round(filesize / 1024 ** 2, 2)}MB"
    elif 1024 ** 3 < filesize < 1024 ** 4:
        return f"{round(filesize / 1024 ** 3, 2)}GB"
    elif 1024 ** 4 < filesize < 1024 ** 5:
        return f"{round(filesize / 1024 ** 4, 2)}TB"
    else:
        return f"{filesize}Bytes"


# 获得目录
def get_list(file_id):
    r = session.get(
        url="https://cloud.189.cn/v2/listFiles.action",
        params={
            "fileId": file_id,
            "inGroupSpace": "false",
            "orderBy": "1",
            "order": "ASC",
            "pageNum": "1",
            "pageSize": "60"
        }
    ).json()
    for file in r["data"]:
        folder_or_file = "" if file["isFolder"] else f"大小: {get_file_size_str(file['fileSize'])}"
        filename = file["fileName"]
        print(f"  {filename}  {folder_or_file} fileID: {file['fileId']}{'' if file['isFolder'] else 'fileID: ' + file['fileId']}")


# 获得文件信息
def get_file_info(file_id):
    r = session.get(f"https://cloud.189.cn/v2/getFileInfo.action?fileId={file_id}").json()
    # print(r)
    return 'http:' + r['downloadUrl'], r['fileName'], r['fileId']


# 创建目录
def creat_folder(folder_name, parent_id):
    r = session.get(
        f'https://cloud.189.cn/v2/createFolder.action?parentId={parent_id}&fileName={folder_name}&noCache=0.4194135200129583').json()
    if 'fileId' in str(r):
        print('文件夹创建成功！')
        return r['fileId']
    else:
        print('创建文件失败！')
        print('错误代码：' + r)


# 删除目录
def delete_folder(fileId, fileName, isFolder, srcParentId):
    taskInfo = [{"fileId": fileId, "fileName": fileName, "isFolder": isFolder, "srcParentId": srcParentId}]
    r = session.post(
        url="https://cloud.189.cn/createBatchTask.action",
        data={
            "type": "DELETE",
            "taskInfos": json.dumps(taskInfo)
        }
    )
    # 判断是否删除成功
    try:
        int(r.text.replace('"', ''))
        print('删除成功!')
    except Exception as e:
        print('删除失败！')
        print('错误代码：' + r.text)


# 获得目录信息
def get_folder_info(file_id):
    r = session.get(
        url="https://cloud.189.cn/v2/listFiles.action",
        params={
            "fileId": file_id,  # 根目录
            "inGroupSpace": "false",
            "orderBy": "1",
            "order": "ASC",
            "pageNum": "1",
            "pageSize": "60"
        }
    ).json()
    return r['data']


def download_file(file_id, filepath):
    url, filename, file_id = get_file_info(file_id)
    r = session.get(url, stream=True)
    with open(filepath + '/' + filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 ** 2):
            f.write(chunk)
        f.close()
    print('正在下载中...')
    print(f"{filename} 下载完成!")


def download_folder(file_name, file_id, filepath):
    if os.path.exists(filepath + os.sep+ file_name):
        pass
    else:
        os.mkdir(filepath + os.sep + file_name)
        print('正在创建目录' + filepath + os.sep + file_name )
    r = get_folder_info(file_id)
    for i in r:
        if i['isFolder']:
            download_folder(i['fileName'], i['fileId'], filepath  + os.sep + file_name)
        else:
            download_file(i['fileId'], filepath  + os.sep + file_name )


# 上传文件
def upload_file(filePath, folder_id):
    file_name = filePath.split(os.sep)[-1]
    session.headers["Referer"] = "https://cloud.189.cn"
    r = session.get(
        url="https://cloud.189.cn/main.action",
        headers={"Host": "cloud.189.cn"}
    )
    sessionKey = re.findall(r"sessionKey = '(.+?)'", r.text)[0]
    filename = os.path.basename(filePath)
    filesize = os.path.getsize(filePath)
    print(f"正在上传: {filename} 大小: {get_file_size_str(filesize)}")
    r = session.post("https://cloud.189.cn/v2/getUserUploadUrl.action")
    upload_url = "https:" + r.json()["uploadUrl"]
    r = session.post(
        url=upload_url,
        data={
            "sessionKey": sessionKey,
            "parentId": folder_id,  # 上传文件夹 根目录
            "albumId": "undefined",
            "opertype": "1",
            "fname": file_name,
        },
        files={
            "Filedata": open(filePath, "rb").read()
        }
    ).json()
    print(f"上传完毕！文件ID：{r['id']} 上传时间: {r['createDate']}")


# 上传文件夹
def upload_folder(folderPath, parent_id):
    folder = folderPath.split(os.sep)[-1]
    new_folder_id = creat_folder(folder, parent_id)
    for i in os.listdir(folderPath):
        if os.path.isfile(folderPath + os.sep + i):
            upload_file(folderPath + os.sep + i, new_folder_id)
        else:
            upload_folder(folderPath + os.sep + i, new_folder_id)


# file_name转化为file_id（要设置为全路径，根目录为我的天翼云盘，具体格式为：我的天翼云盘/我的应用/游戏）
def file_name2file_id(file_name):
    file_list = file_name.split('/')
    t = len(file_list)
    if file_list[0] == '我的天翼云盘':
        id_file = '-11'
        for i in range(t - 1):
            for j in get_folder_info(id_file):
                if j['fileName'] == file_list[i + 1]:
                    id_file = j['fileId']
                else:
                    pass
    else:
        print('目录错误！')
        return Exception
    return id_file


# 用户名称和登陆密码
username = ""
password = ""

if os.getenv('USERNAME'):
    username = os.getenv('USERNAME')
if os.getenv('PASSWORD'):
    username = os.getenv('PASSWORD')
# 登陆
# cookie有一定有效期，建议使用前删除cookie
login()
tc = TC_py()

try:
    if sys.argv[1] == 'upload':
        if len(sys.argv) == 3:
            tc.upload(sys.argv[2], os.sep)
        else:
            tc.upload(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'download':
        if len(sys.argv) == 3:
            tc.download(sys.argv[1], os.sep)
        else:
            tc.download(sys.argv[1], sys.argv[2])
    elif sys.argv[1] == 'list':
        tc.list(sys.argv[2])
    elif sys.argv[1] == 'delete':
        tc.delete(sys.argv[2])
    elif sys.argv[1] == 'creat':
        tc.creat(sys.argv[2])
    elif sys.argv[1] == 'quit':
        print('正在删除cookie')
        os.remove(f"./{username}.cookie")
        exit(-1)
    elif sys.argv[1] == 'help':
        tc.help()
    else:
        print("指令错误")
        tc.help()
    
except IndexError:
    print("缺少参数，请输入help查看详细参数命令")