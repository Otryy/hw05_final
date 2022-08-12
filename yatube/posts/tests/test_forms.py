import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..forms import PostForm
from ..models import Comment, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ContextImageTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.small_gif = (b'\x47\x49\x46\x38\x39\x61\x02\x00'
                         b'\x01\x00\x80\x00\x00\x00\x00\x00'
                         b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
                         b'\x00\x00\x00\x2C\x00\x00\x00\x00'
                         b'\x02\x00\x01\x00\x00\x02\x02\x0C'
                         b'\x0A\x00\x3B')
        cls.uploaded_image = SimpleUploadedFile(name='small.gif',
                                                content=cls.small_gif,
                                                content_type='image/gif')
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(title='Тестовый заголовок',
                                         slug='test-slug',
                                         description='Тестовое описание')
        cls.post = Post.objects.create(text='Тестовый текст',
                                       author=cls.user,
                                       group=cls.group,
                                       image=cls.uploaded_image)
        cls.form = PostForm

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post_with_image(self):
        """Валидная форма создает новую запись с картинкой."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id,
            'image': self.uploaded_image,
        }
        response = self.authorized_client.post(reverse('posts:post_create'),
                                               data=form_data,
                                               follow=True)
        new_post = Post.objects.latest('pub_date')
        self.assertRedirects(
            response, reverse('posts:profile', kwargs={'username': self.user}))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertTrue(
            Post.objects.filter(text=new_post.text,
                                image=new_post.image).exists())
        self.assertEqual(form_data['text'], new_post.text)
        self.assertEqual(self.user, new_post.author)
        self.assertEqual(self.group, new_post.group)

    def test_edit_post_authorized_user(self):
        """Редактирование поста авторизованным пользователем."""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id,
        }
        response = self.authorized_client.post(reverse(
            'posts:post_edit', kwargs={'post_id': self.post.id}),
                                               data=form_data,
                                               follow=True)
        redirect = reverse('posts:post_detail',
                           kwargs={'post_id': self.post.id})
        self.assertRedirects(response, redirect)
        self.assertEqual(Post.objects.count(), post_count)
        self.post.refresh_from_db()
        self.assertEqual(self.post.text, form_data['text'])


class CommentsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='auth',
            email='test@test.ru',
            password='test',
        )
        cls.group = Group.objects.create(
            title='Тестовый заголовок',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст',
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(CommentsTests.user)
        cache.clear()

    def test_add_comments(self):
        """Тест добавления комментария"""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Тестовый текст',
        }
        response = self.authorized_client.post(reverse(
            'posts:add_comment', kwargs={'post_id': self.post.id}),
                                               data=form_data,
                                               follow=True)
        comment = Comment.objects.latest('created')
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertTrue(
            Comment.objects.filter(text=form_data['text']).exists())
        self.assertRedirects(
            response,
            reverse('posts:post_detail', kwargs={'post_id': self.post.id}))
        self.assertEqual(form_data['text'], comment.text)
        self.assertEqual(self.user, comment.author)
