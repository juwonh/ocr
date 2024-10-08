import string
import argparse

import torch
import torch.backends.cudnn as cudnn
import torch.utils.data
import torch.nn.functional as F

from utils import CTCLabelConverter, AttnLabelConverter
from dataset import RawDataset, AlignCollate
from model import Model

import os
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def demo(opt):
    """ model configuration """
    if 'CTC' in opt.Prediction:
        converter = CTCLabelConverter(opt.character)
    else:
        converter = AttnLabelConverter(opt.character)
    opt.num_class = len(converter.character)

    if opt.rgb:
        opt.input_channel = 3
    model = Model(opt)
    print('model input parameters', opt.imgH, opt.imgW, opt.num_fiducial, opt.input_channel, opt.output_channel,
          opt.hidden_size, opt.num_class, opt.batch_max_length, opt.Transformation, opt.FeatureExtraction,
          opt.SequenceModeling, opt.Prediction)
    model = torch.nn.DataParallel(model).to(device)

    # load model
    print('loading pretrained model from %s' % opt.saved_model)
    model.load_state_dict(torch.load(opt.saved_model, map_location=device))

    # prepare data. two demo images from https://github.com/bgshih/crnn#run-demo
    AlignCollate_demo = AlignCollate(imgH=opt.imgH, imgW=opt.imgW, keep_ratio_with_pad=opt.PAD)
    demo_data = RawDataset(root=opt.image_folder, opt=opt)  # use RawDataset
    demo_loader = torch.utils.data.DataLoader(
        demo_data, batch_size=opt.batch_size,
        shuffle=False,
        num_workers=int(opt.workers),
        collate_fn=AlignCollate_demo, pin_memory=True)

    log_file = opt.image_folder + '/_log.txt'
    with open(log_file, 'w') as file:
        # predict
        model.eval()
        with torch.no_grad():
            for image_tensors, image_path_list in demo_loader:
                batch_size = image_tensors.size(0)
                image = image_tensors.to(device)
                # For max length prediction
                length_for_pred = torch.IntTensor([opt.batch_max_length] * batch_size).to(device)
                text_for_pred = torch.LongTensor(batch_size, opt.batch_max_length + 1).fill_(0).to(device)

                if 'CTC' in opt.Prediction:
                    preds = model(image, text_for_pred)

                    # Select max probabilty (greedy decoding) then decode index to character
                    preds_size = torch.IntTensor([preds.size(1)] * batch_size)
                    _, preds_index = preds.max(2)
                    # preds_index = preds_index.view(-1)
                    preds_str = converter.decode(preds_index, preds_size)

                else:
                    preds = model(image, text_for_pred, is_train=False)

                    # select max probabilty (greedy decoding) then decode index to character
                    _, preds_index = preds.max(2)
                    preds_str = converter.decode(preds_index, length_for_pred)
    
                log = open(f'./log_all.txt', 'a')
                # dashed_line = '-' * 80
                # head = f'{"image_path":25s}\t{"predicted_labels":25s}\tconfidence score'                
                # print(f'{dashed_line}\n{head}\n{dashed_line}')
                # log.write(f'{dashed_line}\n{head}\n{dashed_line}\n')

                preds_prob = F.softmax(preds, dim=2)
                preds_max_prob, _ = preds_prob.max(dim=2)
                for img_name, pred, pred_max_prob in zip(image_path_list, preds_str, preds_max_prob):
                    if 'Attn' in opt.Prediction:
                        pred_EOS = pred.find('[s]')
                        pred = pred[:pred_EOS]  # prune after "end of sentence" token ([s])
                        pred_max_prob = pred_max_prob[:pred_EOS]

                    # calculate confidence score (= multiply of pred_max_prob)
                    confidence_score = pred_max_prob.cumprod(dim=0)[-1]                  
                    
                    file_name, ext = os.path.splitext(os.path.basename(img_name))
                    file.write(f'{file_name}\t{pred}\n')
                    log.write(f'{file_name}\t{pred}\n')
                    print(f'{img_name:25s}\t{pred:25s}\t{confidence_score:0.2f}')

                log.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_folder', required=True, help='path to image_folder which contains text images')
    
    parser.add_argument('--workers', type=int, help='number of data loading workers', default=4)
    parser.add_argument('--batch_size', type=int, default=192, help='input batch size')
    parser.add_argument('--saved_model', required=True, help="path to saved_model to evaluation")
    """ Data processing """
    parser.add_argument('--batch_max_length', type=int, default=25, help='maximum-label-length')
    parser.add_argument('--imgH', type=int, default=32, help='the height of the input image')
    parser.add_argument('--imgW', type=int, default=100, help='the width of the input image')
    parser.add_argument('--rgb', default=False, action='store_true', help='use rgb input')
    # parser.add_argument('--character', type=str, default='0123456789abcdefghijklmnopqrstuvwxyz', help='character label')
    parser.add_argument('--character', type=str
                        #, default='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz,.?!"\'$#%&@()*+-/=:<>^'
                     #    , default='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.?!"\'$#%&@()*+-/=:<>^가각간갇갈갉감갑값갓갔강갖갗같갚갛개객갠갤갬갭갯갰갱갸걀걔걘거걱건걷걸검겁것겄겅겆겉겊겋게겐겔겟겠겡겨격겪견결겸겹겻겼경곁계곕곗고곡곤곧골곪곬곯곰곱곳공곶과곽관괄괌광괘괜괭괴괸굉교구국군굳굴굵굶굼굽굿궁궂궈권궐궜궝궤귀귄귈귓규균귤그극근글긁금급긋긍기긴길김깁깃깅깊까깍깎깐깔깜깝깟깡깥깨깬깰깻깼깽꺄꺼꺽꺾껀껄껌껍껏껐껑께껴꼈꼍꼐꼬꼭꼴꼼꼽꼿꽁꽂꽃꽉꽝꽤꽥꾀꾜꾸꾹꾼꿀꿇꿈꿉꿋꿍꿎꿔꿨꿩꿰꿴뀄뀌뀐뀔뀜뀝끄끈끊끌끓끔끕끗끙끝끼끽낀낄낌낍낏낑나낙낚난낟날낡남납낫났낭낮낯낱낳내낵낸낼냄냅냇냈냉냐냔냘냥너넉넋넌널넓넘넙넛넜넝넣네넥넨넬넴넵넷넸넹녀녁년념녔녕녘녜노녹논놀놈놋농높놓놔놨뇌뇨뇩뇽누눅눈눌눔눕눗눠눴뉘뉜뉩뉴늄늅늉느늑는늘늙늠늡능늦늪늬니닉닌닐님닙닛닝닢다닥닦단닫달닭닮닯닳담답닷당닻닿대댁댄댈댐댑댓댔댕댜더덕덖던덜덟덤덥덧덩덫덮데덱덴델뎀뎃뎅뎌뎠뎨도독돈돋돌돔돕돗동돛돝돼됐되된될됨됩됴두둑둔둘둠둡둣둥둬뒀뒤뒬뒷뒹듀듈듐드득든듣들듦듬듭듯등듸디딕딘딛딜딤딥딧딨딩딪따딱딴딸땀땄땅때땐땔땜땝땠땡떠떡떤떨떫떰떱떳떴떵떻떼떽뗀뗄뗍뗏뗐뗑또똑똘똥뙤뚜뚝뚤뚫뚱뛰뛴뛸뜀뜁뜨뜩뜬뜯뜰뜸뜻띄띈띌띔띕띠띤띨띱띵라락란랄람랍랏랐랑랒랗래랙랜랠램랩랫랬랭랴략량러럭런럴럼럽럿렀렁렇레렉렌렐렘렙렛렝려력련렬렴렵렷렸령례로록론롤롬롭롯롱롸롹뢰뢴뢸룃료룐룡루룩룬룰룸룹룻룽뤄뤘뤼류륙륜률륨륭르륵른를름릅릇릉릎리릭린릴림립릿링마막만많맏말맑맘맙맛망맞맡맣매맥맨맬맴맵맷맸맹맺먀먁머먹먼멀멈멋멍멎메멕멘멜멤멥멧멩며멱면멸몄명몇모목몫몬몰몸몹못몽뫼묘무묵묶문묻물묽뭄뭅뭇뭉뭍뭏뭐뭔뭘뭡뭣뮈뮌뮐뮤뮬므믈믐미믹민믿밀밈밉밋밌밍및밑바박밖반받발밝밟밤밥밧방밭배백밴밸뱀뱁뱃뱄뱅뱉뱍뱐버벅번벌범법벗벙벚베벡벤벨벰벱벳벵벼벽변별볍볏볐병볕보복볶본볼봄봅봇봉봐봤뵈뵐뵙부북분붇불붉붐붓붕붙뷔뷰뷴뷸브븐블비빅빈빌빔빕빗빙빚빛빠빡빤빨빳빴빵빻빼빽뺀뺄뺌뺏뺐뺑뺨뻐뻑뻔뻗뻘뻣뻤뻥뻬뼈뼉뼘뽀뽈뽐뽑뽕뾰뿌뿍뿐뿔뿜쁘쁜쁠쁨삐삔삘사삭삯산살삵삶삼삽삿샀상샅새색샌샐샘샙샛샜생샤샨샬샴샵샷샹서석섞선섣설섬섭섯섰성섶세섹센셀셈셉셋셌셍셔션셜셨셰셴셸소속손솔솜솝솟송솥쇄쇠쇤쇳쇼숀숄숍수숙순숟술숨숩숫숭숯숱숲숴쉐쉘쉬쉭쉰쉴쉼쉽슈슐슘슛슝스슥슨슬슭슴습슷승시식신싣실싫심십싯싱싶싸싹싼쌀쌈쌉쌌쌍쌓쌔쌘쌩써썩썬썰썸썹썼썽쎄쎈쏘쏙쏜쏟쏠쏭쏴쐈쐐쐬쑤쑥쑨쒀쒔쓰쓱쓴쓸씀씁씌씨씩씬씰씸씹씻씽아악안앉않알앎앓암압앗았앙앞애액앤앨앰앱앳앴앵야약얀얄얇얌얍얏양얕얗얘얜어억언얹얻얼얽엄업없엇었엉엊엌엎에엑엔엘엠엡엣엥여역엮연열엷염엽엾엿였영옅옆옇예옌옐옙옛오옥온올옭옮옳옴옵옷옹옻와왁완왈왑왓왔왕왜왠왱외왼요욕욘욜욤용우욱운울움웁웃웅워웍원월웜웠웡웨웬웰웸웹위윅윈윌윔윗윙유육윤율윱윳융으윽은을읊음읍응의읜읠이익인일읽잃임입잇있잉잊잎자작잔잖잘잠잡잣잤장잦재잭잰잴잽잿쟀쟁쟈쟉쟤저적전절젊점접젓정젖제젝젠젤젬젭젯져젼졀졌졍조족존졸좀좁종좇좋좌좍좽죄죠죤주죽준줄줌줍줏중줘줬쥐쥔쥘쥬쥴즈즉즌즐즘즙증지직진짇질짊짐집짓징짖짙짚짜짝짠짢짤짧짬짭짰짱째짹짼쨀쨉쨋쨌쨍쩌쩍쩐쩔쩜쩝쩡쩨쪄쪘쪼쪽쫀쫄쫑쫓쫙쬐쭈쭉쭐쭙쯔쯤쯧찌찍찐찔찜찝찡찢찧차착찬찮찰참찹찻찼창찾채책챈챌챔챕챗챘챙챠챤처척천철첨첩첫청체첵첸첼쳄쳇쳉쳐쳔쳤초촉촌촘촛총촨촬최쵸추축춘출춤춥춧충춰췄췌취췬츄츠측츨츰층치칙친칠칡침칩칫칭카칵칸칼캄캅캇캉캐캔캘캠캡캣캤캥캬커컥컨컫컬컴컵컷컸컹케켄켈켐켓켕켜켠켤켭켯켰코콕콘콜콤콥콧콩콰콱콴콸쾅쾌쾡쾨쾰쿄쿠쿡쿤쿨쿰쿵쿼퀀퀄퀘퀭퀴퀵퀸퀼큐큘크큰클큼큽키킥킨킬킴킵킷킹타탁탄탈탉탐탑탓탔탕태택탠탤탬탭탯탰탱터턱턴털텀텁텃텄텅테텍텐텔템텝텡텨톈토톡톤톨톰톱톳통퇴툇투툭툰툴툼퉁퉈퉜튀튄튈튕튜튠튤튬트특튼튿틀틈틉틋틔티틱틴틸팀팁팅파팍팎판팔팜팝팟팠팡팥패팩팬팰팸팻팼팽퍼퍽펀펄펌펍펐펑페펙펜펠펨펩펫펭펴편펼폄폈평폐포폭폰폴폼폿퐁표푭푸푹푼풀품풋풍퓨퓬퓰퓸프픈플픔픕피픽핀필핌핍핏핑하학한할핥함합핫항해핵핸핼햄햅햇했행햐향허헉헌헐험헙헛헝헤헥헨헬헴헵헷헹혀혁현혈혐협혓혔형혜호혹혼홀홈홉홋홍홑화확환활홧황홰홱횃회획횝횟횡효후훅훈훌훑훔훗훤훨훼휄휑휘휙휜휠휩휭휴휼흄흉흐흑흔흘흙흠흡흣흥흩희흰흽히힉힌힐힘힙힝'
                      ,default=' 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.?!"\'$#%&@()*+-/=:<>^가각간갇갈갉감갑값갓갔강갖갗같갚갛개객갠갤갬갭갯갰갱갸걀걔걘거걱건걷걸검겁것겄겅겆겉겊겋게겐겔겟겠겡겨격겪견결겸겹겻겼경곁계곕곗고곡곤곧골곪곬곯곰곱곳공곶과곽관괄괌광괘괜괭괴괸굉교구국군굳굴굵굶굼굽굿궁궂궈권궐궜궝궤귀귄귈귓규균귤그극근글긁금급긋긍기긴길김깁깃깅깊까깍깎깐깔깜깝깟깡깥깨깬깰깻깼깽꺄꺼꺽꺾껀껄껌껍껏껐껑께껴꼈꼍꼐꼬꼭꼴꼼꼽꼿꽁꽂꽃꽉꽝꽤꽥꾀꾜꾸꾹꾼꿀꿇꿈꿉꿋꿍꿎꿔꿨꿩꿰꿴뀄뀌뀐뀔뀜뀝끄끈끊끌끓끔끕끗끙끝끼끽낀낄낌낍낏낑나낙낚난낟날낡남납낫났낭낮낯낱낳내낵낸낼냄냅냇냈냉냐냔냘냥너넉넋넌널넓넘넙넛넜넝넣네넥넨넬넴넵넷넸넹녀녁년념녔녕녘녜노녹논놀놈놋농높놓놔놨뇌뇨뇩뇽누눅눈눌눔눕눗눠눴뉘뉜뉩뉴늄늅늉느늑는늘늙늠늡능늦늪늬니닉닌닐님닙닛닝닢다닥닦단닫달닭닮닯닳담답닷당닻닿대댁댄댈댐댑댓댔댕댜더덕덖던덜덟덤덥덧덩덫덮데덱덴델뎀뎃뎅뎌뎠뎨도독돈돋돌돔돕돗동돛돝돼됐되된될됨됩됴두둑둔둘둠둡둣둥둬뒀뒤뒬뒷뒹듀듈듐드득든듣들듦듬듭듯등듸디딕딘딛딜딤딥딧딨딩딪따딱딴딸땀땄땅때땐땔땜땝땠땡떠떡떤떨떫떰떱떳떴떵떻떼떽뗀뗄뗍뗏뗐뗑또똑똘똥뙤뚜뚝뚤뚫뚱뛰뛴뛸뜀뜁뜨뜩뜬뜯뜰뜸뜻띄띈띌띔띕띠띤띨띱띵라락란랄람랍랏랐랑랒랗래랙랜랠램랩랫랬랭랴략량러럭런럴럼럽럿렀렁렇레렉렌렐렘렙렛렝려력련렬렴렵렷렸령례로록론롤롬롭롯롱롸롹뢰뢴뢸룃료룐룡루룩룬룰룸룹룻룽뤄뤘뤼류륙륜률륨륭르륵른를름릅릇릉릎리릭린릴림립릿링마막만많맏말맑맘맙맛망맞맡맣매맥맨맬맴맵맷맸맹맺먀먁머먹먼멀멈멋멍멎메멕멘멜멤멥멧멩며멱면멸몄명몇모목몫몬몰몸몹못몽뫼묘무묵묶문묻물묽뭄뭅뭇뭉뭍뭏뭐뭔뭘뭡뭣뮈뮌뮐뮤뮬므믈믐미믹민믿밀밈밉밋밌밍및밑바박밖반받발밝밟밤밥밧방밭배백밴밸뱀뱁뱃뱄뱅뱉뱍뱐버벅번벌범법벗벙벚베벡벤벨벰벱벳벵벼벽변별볍볏볐병볕보복볶본볼봄봅봇봉봐봤뵈뵐뵙부북분붇불붉붐붓붕붙뷔뷰뷴뷸브븐블비빅빈빌빔빕빗빙빚빛빠빡빤빨빳빴빵빻빼빽뺀뺄뺌뺏뺐뺑뺨뻐뻑뻔뻗뻘뻣뻤뻥뻬뼈뼉뼘뽀뽈뽐뽑뽕뾰뿌뿍뿐뿔뿜쁘쁜쁠쁨삐삔삘사삭삯산살삵삶삼삽삿샀상샅새색샌샐샘샙샛샜생샤샨샬샴샵샷샹서석섞선섣설섬섭섯섰성섶세섹센셀셈셉셋셌셍셔션셜셨셰셴셸소속손솔솜솝솟송솥쇄쇠쇤쇳쇼숀숄숍수숙순숟술숨숩숫숭숯숱숲숴쉐쉘쉬쉭쉰쉴쉼쉽슈슐슘슛슝스슥슨슬슭슴습슷승시식신싣실싫심십싯싱싶싸싹싼쌀쌈쌉쌌쌍쌓쌔쌘쌩써썩썬썰썸썹썼썽쎄쎈쏘쏙쏜쏟쏠쏭쏴쐈쐐쐬쑤쑥쑨쒀쒔쓰쓱쓴쓸씀씁씌씨씩씬씰씸씹씻씽아악안앉않알앎앓암압앗았앙앞애액앤앨앰앱앳앴앵야약얀얄얇얌얍얏양얕얗얘얜어억언얹얻얼얽엄업없엇었엉엊엌엎에엑엔엘엠엡엣엥여역엮연열엷염엽엾엿였영옅옆옇예옌옐옙옛오옥온올옭옮옳옴옵옷옹옻와왁완왈왑왓왔왕왜왠왱외왼요욕욘욜욤용우욱운울움웁웃웅워웍원월웜웠웡웨웬웰웸웹위윅윈윌윔윗윙유육윤율윱윳융으윽은을읊음읍응의읜읠이익인일읽잃임입잇있잉잊잎자작잔잖잘잠잡잣잤장잦재잭잰잴잽잿쟀쟁쟈쟉쟤저적전절젊점접젓정젖제젝젠젤젬젭젯져젼졀졌졍조족존졸좀좁종좇좋좌좍좽죄죠죤주죽준줄줌줍줏중줘줬쥐쥔쥘쥬쥴즈즉즌즐즘즙증지직진짇질짊짐집짓징짖짙짚짜짝짠짢짤짧짬짭짰짱째짹짼쨀쨉쨋쨌쨍쩌쩍쩐쩔쩜쩝쩡쩨쪄쪘쪼쪽쫀쫄쫑쫓쫙쬐쭈쭉쭐쭙쯔쯤쯧찌찍찐찔찜찝찡찢찧차착찬찮찰참찹찻찼창찾채책챈챌챔챕챗챘챙챠챤처척천철첨첩첫청체첵첸첼쳄쳇쳉쳐쳔쳤초촉촌촘촛총촨촬최쵸추축춘출춤춥춧충춰췄췌취췬츄츠측츨츰층치칙친칠칡침칩칫칭카칵칸칼캄캅캇캉캐캔캘캠캡캣캤캥캬커컥컨컫컬컴컵컷컸컹케켄켈켐켓켕켜켠켤켭켯켰코콕콘콜콤콥콧콩콰콱콴콸쾅쾌쾡쾨쾰쿄쿠쿡쿤쿨쿰쿵쿼퀀퀄퀘퀭퀴퀵퀸퀼큐큘크큰클큼큽키킥킨킬킴킵킷킹타탁탄탈탉탐탑탓탔탕태택탠탤탬탭탯탰탱터턱턴털텀텁텃텄텅테텍텐텔템텝텡텨톈토톡톤톨톰톱톳통퇴툇투툭툰툴툼퉁퉈퉜튀튄튈튕튜튠튤튬트특튼튿틀틈틉틋틔티틱틴틸팀팁팅파팍팎판팔팜팝팟팠팡팥패팩팬팰팸팻팼팽퍼퍽펀펄펌펍펐펑페펙펜펠펨펩펫펭펴편펼폄폈평폐포폭폰폴폼폿퐁표푭푸푹푼풀품풋풍퓨퓬퓰퓸프픈플픔픕피픽핀필핌핍핏핑하학한할핥함합핫항해핵핸핼햄햅햇했행햐향허헉헌헐험헙헛헝헤헥헨헬헴헵헷헹혀혁현혈혐협혓혔형혜호혹혼홀홈홉홋홍홑화확환활홧황홰홱횃회획횝횟횡효후훅훈훌훑훔훗훤훨훼휄휑휘휙휜휠휩휭휴휼흄흉흐흑흔흘흙흠흡흣흥흩희흰흽히힉힌힐힘힙힝'
                        
                        , help='character label')
    parser.add_argument('--sensitive', default=True, action='store_true', help='for sensitive character mode')
    parser.add_argument('--PAD', action='store_true', help='whether to keep ratio then pad for image resize')
    """ Model Architecture """
    parser.add_argument('--Transformation', type=str, required=True, help='Transformation stage. None|TPS')
    parser.add_argument('--FeatureExtraction', type=str, required=True, help='FeatureExtraction stage. VGG|RCNN|ResNet')
    parser.add_argument('--SequenceModeling', type=str, required=True, help='SequenceModeling stage. None|BiLSTM')
    parser.add_argument('--Prediction', type=str, required=True, help='Prediction stage. CTC|Attn')
    parser.add_argument('--num_fiducial', type=int, default=20, help='number of fiducial points of TPS-STN')
    parser.add_argument('--input_channel', type=int, default=1, help='the number of input channel of Feature extractor')
    parser.add_argument('--output_channel', type=int, default=512,
                        help='the number of output channel of Feature extractor')
    parser.add_argument('--hidden_size', type=int, default=512, help='the size of the LSTM hidden state')

    opt = parser.parse_args()

    """ vocab / character number configuration """
    # if opt.sensitive:
    #     opt.character = string.printable[:-6]  # same with ASTER setting (use 94 char).

    cudnn.benchmark = True
    cudnn.deterministic = True
    opt.num_gpu = torch.cuda.device_count()
    print(opt.num_gpu)
    demo(opt)
