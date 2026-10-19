(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun c () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x14 (bvand (bvnot x) c)))
(let ((?x12 (bvsub (bvor x c) x)))
(and (distinct ?x12 ?x14) true))))
(check-sat)
