from python.upload_image import upload_image, upload_images, FireUploadClient

# 单张
result = upload_image("a.jpg")

# 多张
results = upload_images(["a.jpg", "b.jpg"], min_interval=1.0)

# 复用客户端（推荐）
client = FireUploadClient(min_interval=1.0)
r1 = client.upload_image("a.jpg")
r2 = client.upload_image("b.jpg")
