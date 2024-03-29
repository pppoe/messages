import os, json, sys, argparse, shutil, time
import glob, requests, tempfile, time
from datetime import datetime
import minify_html
from mastodon import Mastodon

mastodon = Mastodon(
    access_token = json.load(open('token.json'))['token'],
    api_base_url = 'https://mas.to/'
)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--direct', default=False, action='store_true', help='direct post w/o editing')
    parser.add_argument('--text', default=None, required=False)
    parser.add_argument('--link', default=None, required=False)
    parser.add_argument('--image', default=None, required=False)
    parser.add_argument('--tags', default=None, required=False, help="tag,tag,tag")
    parser.add_argument('--dry', default=False, required=False, action='store_true', help='rebuild locally without pushing')
    parser.add_argument('--site_dir', default="./docs/")
    args = parser.parse_args()

    print (args)

    messages_dir = f'messages/'

    if args.direct: assert (args.text is not None)

    tmp_file = None

    files2add = []

    if not args.dry:
        uuid = str(int(time.time()))
        date_str = datetime.now().strftime('%Y-%m-%d')
        fname = f'{uuid}_{date_str}.json'
        target_fpath = os.path.join(messages_dir, fname)
        temp_file = None

        if args.image is not None:
            if os.path.exists(args.image): # assuming its an image file
                pass
            elif args.image.startswith('http'):
                ext = args.image.lower().split('.')[-1]
                temp_file = tempfile.mktemp() + f'.{ext}'
                with open(temp_file, 'wb') as f:
                    f.write(requests.get(args.image).content)
                args.image = temp_file
            else:
                print (f'Cannot find image {args.image}')
                assert False

        if args.tags is not None and len(args.tags) == 0:
            args.tags = None

        if args.tags is None and "TAGS:" in args.text:
            args.tags = args.text.split("TAGS:")[-1]
            args.text = args.text.split("TAGS:")[0]

        if args.direct:
            template = json.load(open('__template__.json'))
            template['text'] = args.text
            if args.link is not None: template['link'] = args.link
            if args.image is not None: template['image'] = args.image
            if args.tags is not None: template['tags'] = args.tags.split(',')
            template['date'] = date_str
            json.dump(template, open(target_fpath, 'w'))
        else:
            shutil.copyfile('__template__.json', target_fpath)
            os.system(f'vim {target_fpath}')
            template = json.load(open(target_fpath))
            template['date'] = date_str
            assert (len(template['text']) > 0)

        try:
            assert len(template['text']) > 0
            # # post to mas.to, update 'image' and 'interact' fields
            post_content = template['text'] + (f' {template["link"]} ' if len(template["link"]) > 0 else ' ') + ' '.join(f'#{t}' for t in template['tags']) + f' (via https://message.haoxiang.org)'
            if len(template['image']) > 0:
                # if not template['image'].startswith('http'):
                assert os.path.exists(template['image'])
                media = mastodon.media_post(template['image'], description="")
                time.sleep(5)
                ret = mastodon.status_post(post_content, media_ids=media)
                template['image'] = media['url']
                if temp_file is not None and os.path.exists(temp_file): os.remove(temp_file)
            else:
                ret = mastodon.status_post(post_content)
            template['interact'] = ret['url']
            json.dump(template, open(target_fpath, 'w'))
        except Exception as e:
            print (e)
            if temp_file is not None and os.path.exists(temp_file): os.remove(temp_file)
            os.remove(target_fpath)
            print ('Abort')
            sys.exit(0)

        files2add.append(target_fpath)

    def msg2html(fpath):
        return open(fpath).read() + ","

    all_messages = sorted(glob.glob(os.path.join(messages_dir, '*.json')))[::-1]
    page_size = 8
    for i in range(0, len(all_messages), page_size):
        sel = all_messages[i:i+page_size]
        idx = i//page_size
        page_fpath = os.path.join(args.site_dir, f'page{idx+1}.html' if idx > 0 else 'index.html')
        lines = [l for l in open('_page.html').readlines()]
        lean_lines = [l.strip().rstrip() for l in lines]
        page_line_ind = lean_lines.index('__PAGE__')
        lines[page_line_ind] = f'let page = {idx+1}; let pageCount = {len(all_messages)//page_size+1};'
        content_line_ind = lean_lines.index('__CONTENT__')
        lines[content_line_ind] = '\n'.join(msg2html(f) for f in sel) + '\n'
        minified = ''.join(lines) + '\n'
        minified = minify_html.minify('\n'.join(lines), minify_css=True, minify_js=True, remove_processing_instructions=True)
        with open(page_fpath, 'w') as f:
            f.write(minified)
        files2add.append(page_fpath)
    os.system(f'sscli -b https://message.haoxiang.org -r {args.site_dir}')
    files2add.append(os.path.join(args.site_dir,'sitemap.xml'))
    files2add.append(os.path.join(args.site_dir,'sitemap.txt'))
    print (f'files2add = {files2add}')

    if not args.dry:
        for f in files2add:
            os.system(f'git add {f}')
        os.system(f'git commit -m "add post"')
        os.system(f'git push')
