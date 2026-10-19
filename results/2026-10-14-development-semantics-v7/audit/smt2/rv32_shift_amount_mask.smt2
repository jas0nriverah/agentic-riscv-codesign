(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun c () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x334 (bvshl x ((_ zero_extend 27) ((_ extract 4 0) c)))))
(let ((?x331 (bvshl x (bvand c (_ bv31 32)))))
(and (distinct ?x331 ?x334) true))))
(check-sat)
