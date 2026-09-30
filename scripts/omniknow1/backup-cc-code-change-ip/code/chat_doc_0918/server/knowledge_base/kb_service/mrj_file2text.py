import fitz  # PyMuPDF
import json
import re
import os

def is_regex(s):
    special_chars = re.compile(r'[\.\*\+\?\|\(\)\[\]\{\}]')
    return bool(special_chars.search(s))

def potential_title(s):
    if len(s) == 0:
        return False
    index_of_newline = s.find('\n')
    if index_of_newline == -1:
        return re.sub(r'\s+', '', s)
    return re.sub(r'\s+', '', s[:index_of_newline])
    

def get_sub_paragraph(prefix, titles_before, paragraph, patterns, index, max_length=0): # 根据patterns中的匹配项递归拆分
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    if paragraph.find(prefix) == -1 and index > 0: # 必须从第一级标题开始加，否则会统一加上index=0的那部分文本
        title = potential_title(paragraph)
        paragraph = titles_before + f"{prefix}"*index + paragraph
        titles_before = titles_before + f"{prefix}"*index + title
    can_rec = True if index < len(patterns) - 1 else False
    replace_pattern = '\n' if is_regex(patterns[index]) else patterns[index]
    sub_paragraph_list = []
    current_sub_paragraph = ""
    for sub_paragraph in re.split(patterns[index], paragraph):

        if len(current_sub_paragraph) + len(sub_paragraph) + 1 <= max_length: # 用不用maxlength
            if current_sub_paragraph:
                current_sub_paragraph += replace_pattern
            current_sub_paragraph += sub_paragraph
        else:
            if can_rec:
                sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, max_length))
            # else:
            #     sub_paragraph_list.append(current_sub_paragraph) # 用maxlength后需要把不能分割的加进去
            current_sub_paragraph = sub_paragraph
    if current_sub_paragraph:
        if can_rec:
            sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, max_length))
        else:
            sub_paragraph_list.append(current_sub_paragraph)
    return sub_paragraph_list

def extract_text_from_pdf(file_path, use_chunk=False):
    max_length = 0
    # Load the PDF file
    pdf_document = fitz.open(file_path)
    
    # Create a dictionary to hold the extracted text
    # extracted_text = {}
    extracted_text = ""
    # Loop through each page in the PDF
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        # Extract text from the current page
        page_text = page.get_text()
        # Store the extracted text in the dictionary, using the page number as the key
        # extracted_text[page_number] = remove_special_chars(page_text)
        extracted_text += remove_special_chars(page_number, page_text)
    
    # chapter_que = collections.deque(['1. 1. 1'])
    # pattern = r'\d+\.\s*\d+\.\s*\d+'
    pattern = r'(?:\b\d+\.\s*\d+\.\s*\d+|\b第[一二三四五六七八九十]{1,2}[节章]|\b[一二三四五六七八九十]{1,2}、|\b\d+[、.]\d*\
                     |\b\（[一二三四五六七八九十]{1,2}\）)'
    # chapters = re.split(re.compile(pattern), extracted_text)[1:]
    # patterns = [r'\n{2,}', '。\n', '\n']
    patterns = [r'\b第[一二三四五六七八九十]{1,2}[章]', r'\b第[一二三四五六七八九十]{1,2}[节]', r'\b[一二三四五六七八九十]{1,2}、', r'\b\([一二三四五六七八九十]{1,2}\)', r'\n{2,}']
    chapters = [extracted_text]
    chapters = [sub_chapter for chapter in chapters for sub_chapter in get_sub_paragraph('#', '', chapter.strip(), patterns, 0)]

    chapters = [post_split_process(chapter) for chapter in chapters]

    if use_chunk:
        i = 0
        while i < len(chapters) - 1:  # Subtract 1 to avoid an IndexError on the last item
            if len(chapters[i]) < 1000:
                chapters[i] += chapters[i + 1]  # Combine the string with the next string
                del chapters[i + 1]  # Remove the next string from the list
            else:
                i += 1  # Move on to the next index
    total_len = 0
    for i, sub_chapter in enumerate(chapters):
        total_len += len(sub_chapter)
        if len(sub_chapter) > max_length:
            max_length = len(sub_chapter)
    print(f"max: {max_length}, avg: {total_len/(i+1)}")


    
    # Close the PDF file
    pdf_document.close()
    
    return chapters


def remove_special_chars(page_number, text):
    # Define the special characters you want to remove
    special_chars = special_chars = '…■.-'
    # Use re.sub to replace the special characters with an empty string
    text = re.sub(f"[{re.escape(special_chars)}]", "", text)
    # text = re.sub(r'\s+', '\n', text)
    # text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', '', text)
    # text = re.sub(r'\n+', '\n', text)
    # text = f"\npage number {page_number}\n" + text
    return text

def post_split_process(text: str, title_split='**'):
    text = text.replace('\n', title_split, 1)
    title_pos = text.find(title_split)
    if title_pos != -1:
        text = re.sub(r'\s+', '', text[:title_pos]) + text[title_pos:]
    text = re.sub(r'\s+', ' ', text)
    return text

if __name__ == "__main__":
    extracted_text_list = []
    directory = "raw_data"
    file_path_list = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    # Construct the complete file paths
    # file_paths = [os.path.join(directory, f) for f in file_path_list]
    file_path_list = ["/home/cc007/datagen/raw_data/M3000S_2.pdf"]
    for file_path in file_path_list:
        file_path = os.path.join(directory, file_path)
        extracted_text_list.extend(extract_text_from_pdf(file_path))

    # Optionally, save the extracted text to a JSON file
    with open("extracted_text4.json", "w", encoding="utf-8") as f:
        json.dump(extracted_text_list, f, ensure_ascii=False, indent=4)


