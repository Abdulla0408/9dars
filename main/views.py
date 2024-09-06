from django.shortcuts import render, redirect
from . import models
from random import choice, sample
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .models import Quiz, AnswerDetail
from io import BytesIO

def index(request):
    return render(request, 'index.html')


def quizList(request):
    images = [
        'https://st2.depositphotos.com/2769299/7314/i/450/depositphotos_73146775-stock-photo-a-stack-of-books-on.jpg',
        'https://img.freepik.com/free-photo/creative-composition-world-book-day_23-2148883765.jpg',
        'https://profit.pakistantoday.com.pk/wp-content/uploads/2018/04/Stack-of-books-great-education.jpg',
        'https://live-production.wcms.abc-cdn.net.au/73419a11ea13b52c6bd9c0a69c10964e?impolicy=wcms_crop_resize&cropH=1080&cropW=1918&xPos=1&yPos=0&width=862&height=485',
        'https://live-production.wcms.abc-cdn.net.au/398836216839841241467590824c5cf1?impolicy=wcms_crop_resize&cropH=2813&cropW=5000&xPos=0&yPos=0&width=862&height=485',
        'https://images.theconversation.com/files/45159/original/rptgtpxd-1396254731.jpg?ixlib=rb-4.1.0&q=45&auto=format&w=1356&h=668&fit=crop'
    ]
    
    if request.user.is_authenticated:
        quizes = models.Quiz.objects.filter(author=request.user)
    else:
        quizes = []
    # images = sample(len(quizes), images)

    quizes_list = []

    for quiz in quizes:
        quiz.img = choice(images)
        quizes_list.append(quiz)

    return render(request, 'quiz-list.html', {'quizes':quizes_list})


def quizDetail(request, id):
    quiz = models.Quiz.objects.get(id=id)
    questions = quiz.questions.all()  # Bog'langan obyektlarni oldindan yuklash
    return render(request, 'quiz-detail.html', {'quiz': quiz, 'questions': questions})


def questionDelete(request, id, pk):
    models.Question.objects.get(id=id).delete()
    return redirect('quizDetail', id=pk)


def createQuiz(request):
    if request.method == 'POST':
        quiz = models.Quiz.objects.create(
            name = request.POST['name'],
            amount = request.POST['amount'],
            author = request.user
        )
        return redirect('quizDetail', quiz.id)
    return render(request, 'quiz-create.html')


def questionCreate(request, id):
    quiz = models.Quiz.objects.get(id=id)
    if request.method == 'POST':
        question_text = request.POST['name']
        true = request.POST['true']
        false_list = request.POST.getlist('false-list')

        question = models.Question.objects.create(
            name = question_text,
            quiz = quiz,
        )
        question.save()
        models.Option.objects.create(
            question = question,
            name = true,
            correct = True,
        )

        for false in false_list:
            models.Option.objects.create(
                name = false,
                question = question,
            )
        return redirect('quizList')

    return render(request, 'question-create.html', {'quiz':quiz})


def questionDetail(request, id):
    question = models.Question.objects.get(id=id)
    return render(request, 'question-detail.html', {'question':question})


def deleteOption(request, ques, option):
    question = models.Question.objects.get(id=ques)
    models.Option.objects.get(question=question, id=option).delete()
    return redirect('questionDetail', id=ques)


def resultsView(request):
    quizzes = models.Quiz.objects.all()
    results = []
    for quiz in quizzes:
        questions = models.Question.objects.filter(quiz=quiz)
        total_questions = questions.count()
        correct_answers = models.Option.objects.filter(question__quiz=quiz, correct=True).count()
        incorrect_answers = models.Option.objects.filter(question__quiz=quiz, correct=False).count()
        attempts = models.AnswerDetail.objects.filter(question__quiz=quiz).count()
        if total_questions > 0:
            correct_answer_percentage = (correct_answers / total_questions) * 100
        else:
            correct_answer_percentage = 0
        results.append({
            'quiz_name': quiz.name,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'attempts': attempts,
            'correct_answer_percentage': round(correct_answer_percentage, 2),
        })
    return render(request, 'answer/results.html', {'results': results})

def export_quiz_answers(request, quiz_id):
    quiz = models.Quiz.objects.get(id=quiz_id)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Quiz Answers"

    # Sarlavhalarni qo'shish
    worksheet.append(["User", "Question", "Selected Option", "Correct/Incorrect"])

    # Answer emas, AnswerDetail obyektlarini olish
    for answer_detail in models.AnswerDetail.objects.filter(answer__question__quiz=quiz).select_related('answer__author', 'question', 'user_choice'):
        worksheet.append([
            answer_detail.answer.author.username,
            answer_detail.question.name,
            answer_detail.user_choice.name,
            "Correct" if answer_detail.is_correct else "Incorrect"
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=quiz_{quiz_id}_answers.xlsx'
    workbook.save(response)
    return response

def generate_quiz_pdf(request, quiz_id):
    # PDF yaratish
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont('Helvetica', 12)  # 'DejaVuSans' o'rniga 'Helvetica' ni ishlatamiz

    # Quiz ma'lumotlarini olish
    quiz = Quiz.objects.get(id=quiz_id)
    answer_details = AnswerDetail.objects.filter(answer__question__quiz=quiz).select_related(
        'answer__author', 'question', 'selected_option'
    ).prefetch_related('question__options')

    # PDF ga ma'lumotlarni yozish
    p.drawString(100, 750, f"Quiz nomi: {quiz.name}")
    y = 700
    for detail in answer_details:
        if y < 100:  # Yangi sahifa
            p.showPage()
            p.setFont('Helvetica', 12)
            y = 750
        p.drawString(100, y, f"Foydalanuvchi: {detail.answer.author.username}")
        y -= 20
        p.drawString(100, y, f"Savol: {detail.question.name}")
        y -= 20
        p.drawString(100, y, f"Tanlangan javob: {detail.selected_option.name if detail.selected_option else 'Javob berilmagan'}")
        y -= 20
        correct_option = detail.question.options.filter(is_correct=True).first()
        p.drawString(100, y, f"To'g'ri javob: {correct_option.name if correct_option else 'Aniqlanmagan'}")
        y -= 20
        p.drawString(100, y, f"Natija: {'Togri' if detail.is_correct else 'Notogri'}")
        y -= 40

    # PDF ni yakunlash
    p.showPage()
    p.save()

    # PDF ni yuborish
    buffer.seek(0)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=quiz_{quiz_id}_natijalar.pdf'
    response.write(buffer.getvalue())
    buffer.close()
    return response

def finish_quiz(request, quiz_id):
    # ... quiz yakunlash logikasi ...
    return redirect('generate_quiz_pdf', quiz_id=quiz_id)
