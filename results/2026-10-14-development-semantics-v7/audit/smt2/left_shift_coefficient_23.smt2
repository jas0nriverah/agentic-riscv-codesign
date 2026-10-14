(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x252 (bvmul x (_ bv8388608 32))))
(let ((?x250 (bvshl x (_ bv23 32))))
(and (distinct ?x250 ?x252) true))))
(check-sat)
