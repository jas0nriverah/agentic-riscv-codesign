(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x306 (bvmul x (_ bv536870912 32))))
(let ((?x304 (bvshl x (_ bv29 32))))
(and (distinct ?x304 ?x306) true))))
(check-sat)
