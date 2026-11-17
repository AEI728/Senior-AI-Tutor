"""Original draft course seeds. No expert, copyright or effectiveness claims."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
definitions = [
    ('calligraphy','书法入门','calligraphy-lines','纸上横线练习', ['准备纸和笔，选择舒适坐姿。','轻轻画一条横线，不必用力握紧。','放松手腕，再画一条横线，观察两次的变化。'], '手腕不适请停止；不要求使用毛笔。'),
    ('photography','手机摄影','phone-composition','手机构图入门', ['选择一件不含他人隐私的静物。','站稳后打开手机相机，将主体放入画面。','改变主体在画面中的位置，选择喜欢的一张。'], '不要边走边拍，不在道路或危险边缘拍摄。'),
    ('music','节奏入门','rhythm-basics','轻拍节奏入门', ['坐稳，放松双手和肩膀。','用手指在桌面轻拍，保持舒适音量。','按自己舒适的速度重复短节奏，疲劳时休息。'], '不要求用力敲击；不适时停止。')]
for sid,name,cid,title,texts,note in definitions:
    value={'skill':{'id':sid,'name':name,'category':sid}, 'course':{
        'id':cid,'title':title+'（内部测试）','version':1,'review_status':'draft',
        'asset_license_status':'internal_demo','locale':'zh-CN','media_path':None,
        'learning_goal':'通过原创文字与流程示意了解'+title+'，不作为专业教学认证。',
        'prerequisites':['准备安全、安静且方便休息的环境。'],
        'steps':[{'no':i+1,'title':['准备','尝试','回顾'][i],'instruction':s,
                  'explanation':'按舒适速度练习，不追求一次完成。','safety_notes':[note],
                  'completion_rule':'用户明确自述本步骤完成','source_role':'platform_editor'} for i,s in enumerate(texts)],
        'faq':[{'step_no':1,'question':'一定要一次做好吗？','answer':'不需要，可以暂停、复讲，按自己的节奏尝试。','verified':False},
               {'step_no':2,'question':'不舒服怎么办？','answer':'停止练习、放稳工具并休息，必要时寻求帮助。','verified':False}]}}
    (root / 'data/courses' / (cid+'.zh-CN.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
