from urllib.parse import urlencode
def convert_generate_file_to_download_url(local_path,filename):
    parameters = urlencode({"filepath": local_path, "filename":filename})
    url_path = f"/knowledge_base/download_file?" + parameters
    return url_path