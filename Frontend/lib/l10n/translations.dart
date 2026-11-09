const englishText = <String, String>{
  "آشنایی": "Welcome",
  "حساب": "Account",
  "گفتگو": "Conversation",
  "آماده‌سازی": "Your reminder",
  "مطالعه": "Reading",
  "پایان": "Done",
  "شروع": "Start",
  "ادامه": "Continue",
  "بازگشت": "Back",
  "قبلی": "Back",
  "ورود": "Sign in",
  "ورود به حساب": "Sign in",
  "برای چیزی که برات مهمه، وقت بذار": "Make time for what matters to you",
  "مویرای همراه مطالعه‌ی توئه؛ با یادآوری هدفت، کمکت می‌کنه وقتی حواست پرت شد دوباره برگردی.":
      "Moirai is your reading companion. A reminder of your goal helps you return when you get distracted.",
  "از هدفت بگو": "Tell us about your goal",
  "در یک گفتگوی کوتاه، از آینده‌ای که می‌خوای می‌گی تا یادآور شخصی‌ات ساخته بشه.":
      "Describe the future you want in a short conversation to create your personal reminder.",
  "فایلت رو انتخاب کن": "Choose your PDF",
  "کتاب، مقاله یا جزوه‌ات رو به‌صورت PDF باز کن و بخون.":
      "Open a book, paper, or notes as a PDF and start reading.",
  "وقتی حواست رفت، برگرد": "Find your way back",
  "یادآورت بهت یادآوری می‌کنه برای چی شروع کردی.":
      "Your reminder brings you back to why you started.",
  "ایجاد حساب کاربری ": "Create your account",
  "برای ذخیره‌ی گفتگو و یادآورت، یک حساب بساز.":
      "Create an account to save your conversation and reminder.",
  "حساب داری؟ وارد شو": "Already have an account? Sign in",
  "بساز و ادامه بده": "Create account",
  "یک شناسه برای خودت انتخاب کن": "Choose a username",
  "مثلاً sara123": "For example, sara123",
  "یک رمز ساده (حداقل ۴ حرف)": "Password (at least 4 characters)",
  "شناسه حداقل ۳ حرف باشد": "Use at least 3 characters for your username.",
  "شناسه حداکثر ۳۲ حرف باشد":
      "Use no more than 32 characters for your username.",
  "رمز حداقل ۴ حرف باشد": "Use at least 4 characters for your password.",
  "این شناسه قبلاً انتخاب شده — یکی دیگر امتحان کن":
      "That username is taken. Try another.",
  "خوش برگشتی 👋": "Welcome back 👋",
  "شناسه و رمزت را وارد کن تا از همان‌جایی که بودی ادامه بدهی.":
      "Sign in to continue where you left off.",
  "شناسه‌ی تو": "Username",
  "رمز": "Password",
  "شناسه را وارد کن": "Enter your username.",
  "رمز را وارد کن": "Enter your password.",
  "کد یا رمز درست نیست": "The username or password is incorrect.",
  "حساب نداری؟ ثبت‌نام": "New here? Create an account",
  "ثبت‌نام": "Create account",
  "قدم‌ها": "Steps",
  "هدف": "Goal",
  "زمان": "Time",
  "مکان": "Place",
  "کار": "Action",
  "اطراف": "Surroundings",
  "افراد": "People",
  "احساس": "Feeling",
  "پاسخ خود را بنویس...": "Write your answer…",
  "گفتگو کمکت نمی‌کنه؟ پاسخ‌ها رو دستی بنویس ":
      "Prefer a form? Write your answers yourself",
  "یکی رو انتخاب کن و به دلخواه تغییرش بده":
      "Choose an idea and make it your own",
  "الان نتونستم نمونه بیارم — با جمله‌ی خودت شروع کن، هرچقدر کوتاه.":
      "Ideas aren't available right now. Start with a few words of your own.",
  "مشکلی در ارتباط با سرور رخ داد. دوباره تلاش کن.":
      "Couldn't connect. Please try again.",
  "مشکل در اتصال به سرور": "Connection problem",
  "در حال ساختن تصویر آینده‌ات... چند لحظه صبر کن 🌱":
      "Creating your future image… 🌱",
  "در همین لحظه، یادآورهای شخصی تو در حال ساخته شدن هستند... 🎨":
      "Your personal reminder is being created… 🎨",
  "تصویر آینده‌ات آماده است ✅": "Your image is ready ✅",
  "یادآورهای شخصی‌ات آماده‌ان ✅": "Your personal reminder is ready ✅",
  "ساخت یادآورها الان جواب نداد؛ نگران نباش، یک یادآور پیش‌فرض جایگزینش شد.":
      "We couldn't create your image. Please try again.",
  "تلاش دوباره": "Try again",
  "گفتگو چطور بود؟": "How was the conversation?",
  "اختیاری · ۱ ضعیف، ۵ عالی": "Optional · 1 poor, 5 great",
  "ثبت نظر": "Save feedback",
  "در حال ثبت…": "Saving…",
  "ثبت شد، ممنون!": "Saved, thank you!",
  "ثبت نشد؛ دوباره امتحان کن.": "Couldn't save. Please try again.",
  "لحظه‌ای به تصویر نگاه کن و خودت رو در این آینده تصور کن.":
      "Take a moment to look at the image and picture yourself in this future.",
  "وقتی آماده بودی، دکمه‌ی «ادامه» را بزن 🌱": "Continue when you're ready 🌱",
  "PDF تا ۳۰ مگابایت": "PDF up to 30 MB",
  "انتخاب PDF": "Choose PDF",
  "در حال انتخاب…": "Opening file picker…",
  "فقط در مرورگر باز می‌شه؛ بعد از تازه‌سازی، دوباره انتخابش کن.":
      "Opened only in your browser. Select it again after refreshing.",
  "انتخاب فایل انجام نشد. دوباره تلاش کن.":
      "Couldn't select the file. Please try again.",
  "فایل PDF باید کمتر از ۳۰ مگابایت باشد.": "Choose a PDF smaller than 30 MB.",
  "لطفاً یک فایل PDF معتبر انتخاب کن.": "Please choose a valid PDF.",
  "افزونه‌ی یادآور": "Reminder extension",
  "یادآوری بیرون از مویرای؛ نصب اختیاری.":
      "Reminders outside Moirai. Installation is optional.",
  "یادآورهای داخل مویرای به افزونه نیاز ندارن.":
      "Reminders inside Moirai work without the extension.",
  "می‌تونی بدون افزونه ادامه بدی.": "You can continue without the extension.",
  "تصویر آینده‌ات هنوز آماده نشده — چند لحظه صبر کن 🌱":
      "Your image isn't ready yet. Please wait a moment 🌱",
  "دانلود افزونه": "Download extension",
  "بررسی اتصال": "Check connection",
  "متصل شد ✅": "Connected ✅",
  "متصل نشد — مطمئن شو افزونه نصب و فعاله، بعد دوباره امتحان کن.":
      "Not connected. Check that the extension is installed and enabled, then try again.",
  "باز کردن فایل": "Open PDF",
  "فایل تو": "Your PDF",
  "فایل باز نشد. فایل ممکن است آسیب‌دیده یا رمزدار باشد.":
      "Couldn't open this PDF. It may be damaged or password protected.",
  "انتخاب مجدد": "Choose another file",
  "یک نفس عمیق بکش... 🌬️": "Take a deep breath… 🌬️",
  "با ریتم خودت پیش برو.": "Go at your own pace.",
  "هر وقت خواستی، تمامش کن.": "Finish whenever you're ready.",
  "پایان مطالعه": "Finish reading",
  "برای ادامه ضربه بزن": "Tap to continue",
  "برای چیزی که برات مهم بود، وقت گذاشتی 🌱":
      "You made time for what matters 🌱",
  "وقت یک استراحت کوتاهه.": "Time for a short break.",
  "ضعیف": "Poor",
  "عالی": "Great",
  "سخت": "Difficult",
  "آسان": "Easy",
  "۱. هدف بلندمدتت چیه؟": "1. What is your long-term goal?",
  "۲. اون لحظه که به هدفت رسیدی، دقیقاً کجایی؟":
      "2. Where are you in that future moment?",
  "۳. اون لحظه کِی اتفاق می‌افته؟": "3. When does that moment happen?",
  "۴. توی اون لحظه داری چه کاری می‌کنی؟":
      "4. What are you doing in that moment?",
  "۵. دور و برت چه چیزهایی می‌بینی؟": "5. What can you see around you?",
  "۶. تنهایی یا کسی باهاته؟": "6. Are you alone or with someone?",
  "۷. اون لحظه چه حس خوبی داری؟": "7. What positive feeling do you notice?",
  "مثلاً پیشرفت در کار، تحصیل، یا یک پروژه‌ی شخصی":
      "For example, work, education, or a personal project",
  "شهر و مکان رو دقیق بگو — انگار همین الان اونجایی":
      "Name the place as if you were there now",
  "چند ماه یا چند سال دیگه؟ چه فصلی؟ صبح یا عصر؟":
      "How far from now? Which season and time of day?",
  "مثلاً حرف می‌زنی، ارائه می‌دی، چیزی می‌خونی یا می‌نویسی":
      "For example, speaking, presenting, reading, or writing",
  "چند تا چیز رو نام ببر — مثلاً میز، لپ‌تاپ، پنجره، درخت":
      "Name a few things, such as a desk, laptop, window, or tree",
  "مثلاً دوست، همکار، استاد یا خانواده":
      "For example, a friend, colleague, teacher, or family member",
  "مثلاً آرامش، غرور، اعتماد به نفس یا هیجان":
      "For example, calm, pride, confidence, or excitement",
  "ثبت نهایی پاسخ‌ها؟": "Submit your answers?",
  "بله، ثبت کن": "Yes, submit",
  "۱. دانلود و خارج کردن فایل از حالت فشرده\n۲. باز کردن chrome://extensions و روشن کردن Developer mode\n۳. زدن Load unpacked و انتخاب پوشه‌ی افزونه\n۴. برگرد اینجا و «بررسی اتصال» رو بزن":
      "1. Download and unzip the extension.\n2. Open chrome://extensions and enable Developer mode.\n3. Choose Load unpacked and select the extension folder.\n4. Return here and choose Check connection.",
  "بعد از ثبت، دیگه نمی‌تونی به گفتگو برگردی و از اون راه ادامه بدی. اگه هنوز می‌خوای گفتگو رو امتحان کنی، «بازگشت» رو بزن.":
      "Submitting saves this scene and closes the conversation. Choose Back if you want to keep chatting.",
  "لطفاً همه‌ی بخش‌ها رو کامل کن.": "Please complete each part.",
  "پاسخ‌ها ثبت شد.": "Your answers are saved.",
  "حساب نداری؟ از اینجا بساز": "New here? Create an account",
  "بازگشت به گفتگو": "Back to conversation",
  "همه‌ی ۷ سوال را کامل کن": "Complete all 7 answers",
  "ثبت نهایی": "Save scene",
  "نوشتن دستی پاسخ‌ها ✍️": "Write your answers ✍️",
  "همون ۷ سوال گفتگو، این بار با جای خالی برای نوشتن. هر چی دقیق‌تر بنویسی، تصویرت شخصی‌تر می‌شه. اگه هنوز همه‌ی جزئیات رو نمی‌دونی اشکالی نداره — همون چیزی که به ذهنت می‌رسه کافیه.":
      "The same 7 questions, in a form. Use your own details to make the image personal. Write what comes to mind; it does not need to be perfect.",
  "با ریتم خودت پیش برو.\nهر وقت خواستی، تمامش کن.":
      "Go at your own pace.\nFinish whenever you are ready.",
  "ابتدا باید وارد شوی.": "Please sign in first.",
  "قبلاً از راه گفتگو ثبت کردی؛ دیگه نمی‌شه دستی ثبت کرد.":
      "Your scene is already saved from the conversation.",
  "مشکلی در ارتباط با سرور پیش اومد. دوباره تلاش کن.":
      "Could not connect. Please try again.",
};
