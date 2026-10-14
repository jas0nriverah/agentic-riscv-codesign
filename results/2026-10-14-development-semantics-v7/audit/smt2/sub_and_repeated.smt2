(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun c () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x18 (bvand x (bvnot c))))
(let ((?x16 (bvsub x (bvand x c))))
(and (distinct ?x16 ?x18) true))))
(check-sat)
