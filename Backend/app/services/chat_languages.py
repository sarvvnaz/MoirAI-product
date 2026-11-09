QUESTIONS_EN = [
    'What long-term goal does the task you want to work on help you move toward?',
    'When do you picture that future moment? How far from now, and what time of day?',
    'Where are you in that moment? For example, at home, at work, or somewhere else you have in mind.',
    'What are you doing in that moment?',
    'What are one or two things you can see around you?',
    'Are you alone in that moment, or is someone with you?',
    'How do you feel when you picture yourself in that moment?',
]
LABELS_EN = ['Goal', 'Time', 'Place', 'Action', 'Surroundings', 'People', 'Feeling']
INTRO_EN = ("Let's picture a specific moment in a future that matters to you. "
            "It doesn't need to be a big milestone or a prediction. "
            "I'll ask one question at a time; use the lightbulb if you need an idea.\n\n" + QUESTIONS_EN[0])
IDEAS_EN = {
    'goal': ['Grow in my work.', 'Finish a course I care about.', 'Complete a personal project.'],
    'when': ['A morning next spring.', 'An evening later this year.', 'A weekend a few months from now.'],
    'where': ['Somewhere I enjoy working.', 'A quiet place at home.', 'A place that matters to me.'],
    'action': ['Sharing something I have made.', 'Explaining what I have learned.', 'Finishing something important to me.'],
    'objects': ['A few everyday objects around me.', 'Something on my desk.', 'Something I can see through the window.'],
    'who': ['On my own.', 'With a friend or colleague.', 'With someone I care about.'],
    'feeling': ['Calm.', 'Proud.', 'Confident and hopeful.'],
}
