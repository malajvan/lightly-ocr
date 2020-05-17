import torch

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


# https://github.com/meijieru/crnn.pytorch/blob/master/utils.py
class CTCLabelConverter(object):
    #  Convert between text-label and text-index

    def __init__(self, character):
        # character (str): set of the possible characters.
        dict_character = list(character)

        self.dict = {}
        for i, char in enumerate(dict_character):
            # NOTE: 0 is reserved for 'blank' token required by CTCLoss
            self.dict[char] = i + 1

        self.character = [
            '[blank]'
        ] + dict_character  # dummy '[blank]' token for CTCLoss (index 0)

    def encode(self, text, batch_max_len=25):
        # convert text-label into text-index.
        length = [len(s) for s in text]
        text = ''.join(text)
        text = [self.dict[char] for char in text]

        return (torch.IntTensor(text), torch.IntTensor(length))

    def decode(self, text_index, length):
        # convert text-index into text-label.
        texts = []
        index = 0
        for l in length:
            t = text_index[index:index + l]

            char_list = []
            for i in range(l):
                if t[i] != 0 and (not (i > 0 and t[i - 1] == t[i])
                                  ):  # removing repeated characters and blank.
                    char_list.append(self.character[t[i]])
            text = ''.join(char_list)

            texts.append(text)
            index += l
        return texts


class AttnLabelConverter(object):
    # Convert between text-label and text-index

    def __init__(self, character):
        # character (str): set of the possible characters.
        # [GO] for the start token of the attention decoder. [s] for end-of-sentence token.
        list_token = ['[GO]', '[s]']  # ['[s]','[UNK]','[PAD]','[GO]']
        list_character = list(character)
        self.character = list_token + list_character

        self.dict = {}
        for i, char in enumerate(self.character):
            # print(i, char)
            self.dict[char] = i

    def encode(self, text, batch_max_len=25):
        # convert text-label into text-index.

        length = [len(s) + 1 for s in text]  # +1 for [s] at end of sentence.
        # batch_max_len = max(length) # this is not allowed for multi-gpu setting
        batch_max_len += 1
        # additional +1 for [GO] at first step. batch_text is padded with [GO] token after [s] token.
        batch_text = torch.LongTensor(len(text), batch_max_len + 1).fill_(0)
        for i, t in enumerate(text):
            text = list(t)
            text.append('[s]')
            text = [self.dict[char] for char in text]
            batch_text[i][1:1 + len(text)] = torch.LongTensor(
                text)  # batch_text[:, 0] = [GO] token
            return (batch_text.to(device), torch.IntTensor(length).to(device))

    def decode(self, text_index, length):
        # convert text-index into text-label.
        texts = []
        for index, l in enumerate(length):
            text = ''.join([self.character[i] for i in text_index[index, :]])
            texts.append(text)
        return texts


class Averager(object):
    # Compute average for torch.Tensor, used for loss average.

    def __init__(self):
        self.reset()

    def add(self, v):
        count = v.data.numel()
        v = v.data.sum()
        self.n_count += count
        self.sum += v

    def reset(self):
        self.n_count = 0
        self.sum = 0

    def val(self):
        res = 0
        if self.n_count != 0:
            res = self.sum / float(self.n_count)
        return res


# implements levenshtein edit-distance
# lev a,b(|a|,|b|) == max(|a|,|b|) if min(|a|,|b|)== 0 else min([lev a,b(|a|-1,|b|)+1], [lev a,b(|a|,|b|-1)+1], [lev a,b(|a|-1, |b|-1)+1])
