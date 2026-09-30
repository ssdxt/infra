import os
code_line_count = 0
codes = []
for filename in os.listdir():
    if os.path.isdir(filename):
        print(f"---------{filename}-------------")
        
        for file in os.listdir(filename):
            if file.endswith(".py"):
                
                file_path = os.path.join(filename, file)
                with open(file_path) as f: 
                    pys = f.readlines()
                    with open("codes.txt","a", encoding="utf-8") as f:
                        f.write(f"----------------------\n")
                        f.write(file+"\n")
                        f.write(f"----------------------\n")
                        # f.write("\n".join(pys))
                        f.write("".join(pys))

                        
                    codes += pys
                    print(len(pys))
                    
            if len(codes) > 3000:
                break
print(len(codes))
