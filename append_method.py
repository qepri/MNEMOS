
with open('app/services/rag.py', 'r', encoding='utf-8') as f:
    original = f.read()

with open('app/services/rag_method_dump.py', 'r', encoding='utf-8') as f:
    new_method = f.read()

with open('app/services/rag.py', 'w', encoding='utf-8') as f:
    f.write(original + "\n\n" + new_method)

print("Successfully appended method to rag.py")
