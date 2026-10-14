(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x25 (bvneg y)))
(let ((?x26 (bvadd x ?x25)))
(let ((?x24 (bvsub x y)))
(and (distinct ?x24 ?x26) true)))))
(check-sat)
