import UnityPy
from PIL import Image
from tkinter.filedialog import askopenfilename
import UnityPy.config

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.42f1"


def get_texture(env, card=True, land=False):
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "Texture2D":
            if card:
                if data.image.size[0] == 512:
                    return data
            elif land:
                if data.image.size[0] != 1024:
                    return data
            else:
                return data
    return None


def open_image(data, path):

    data.image.save(path)

    return data
    # edit texture


def save_image(data, new_path, src, env):

    data.image = Image.open(new_path)
    data.save()
    with open(src, "wb") as f:
        f.write(env.file.save())


def load(path):
    return UnityPy.load(path)


# OTHER_PATH =
# if __name__ == "__main__":
#     PATH_TO_FILE = askopenfilename()
#     src = PATH_TO_FILE

#     env = UnityPy.load(src)
#     data = get_texture(env)
#     d = open_image(
#         data, PATH
#     )
# save_image(
#     d, OTHER_PATH, src, env
# )
