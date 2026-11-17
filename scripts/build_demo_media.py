"""Original animated procedure cards; explicitly not expert/filmed teaching."""
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

root=Path(__file__).resolve().parents[1]
folder=root/'media';folder.mkdir(exist_ok=True)
font_path=next((p for p in [Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),None)
def font(n):return ImageFont.truetype(str(font_path),n) if font_path else ImageFont.load_default()
for path in sorted((root/'data/courses').glob('*.json')):
    c=json.loads(path.read_text('utf-8'))['course']
    with tempfile.TemporaryDirectory() as temp:
        for i,step in enumerate(c['steps']):
            im=Image.new('RGB',(960,540),'#f8f5ee');d=ImageDraw.Draw(im)
            d.rounded_rectangle((34,34,926,506),25,fill='#e5ead8')
            d.text((65,58),'小伴 · 原创流程示意',font=font(27),fill='#2f4942')
            d.text((65,113),f"{i+1:02d}  {step['title']}",font=font(42),fill='#2f4942')
            text=step['instruction']
            for line in range(0,len(text),21):d.text((65,200+line//21*51),text[line:line+21],font=font(32),fill='#263b32')
            d.text((65,440),'内部测试 · 未经专业审核 · 不代替动作核验',font=font(22),fill='#705b42')
            d.ellipse((760,340,840,380),fill='#6e8554');d.rectangle((799,370,805,418),fill='#4f6c3f');d.polygon([(765,414),(840,414),(825,461),(778,461)],fill='#b98260')
            im.save(Path(temp)/f'{i:03d}.png')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-framerate','1/5','-i',str(Path(temp)/'%03d.png'),'-vf','fps=24','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(folder/(c['id']+'.mp4'))],check=True)
    print('Generated',c['id'])
