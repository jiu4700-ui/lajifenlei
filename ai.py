from aip import AipImageClassify

APP_ID = "123709325"
API_KEY = "k298aeiNErwKFlKraadVbxa6"
SECRET_KEY = "2iestVDtAyEWnM67yCZXLF50M0rHqc1i"

client = AipImageClassify(APP_ID, API_KEY, SECRET_KEY)


def recognize_image(image_path):

    with open(image_path, 'rb') as f:
        image = f.read()

    result = client.advancedGeneral(image)

    # 百度返回 top1
    if "result" in result and len(result["result"]) > 0:
        return result["result"][0]["keyword"]

    return "未知"